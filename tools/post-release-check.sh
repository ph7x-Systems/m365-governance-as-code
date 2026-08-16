#!/usr/bin/env bash
#
# THE GATE AFTER THE UPLOAD. A version is not released because PyPI accepted it.
#
#   ./tools/post-release-check.sh 1.0.0b4
#
# WHY THIS EXISTS. `release-check.sh` proves the wheel this repository builds.
# It says nothing about the wheel a user downloads, and the two have been
# different: 1.0.0b2 shipped a README whose install command resolved to
# nothing, and 1.0.0b4 shipped one that told the reader to install 1.0.0b3.
# Both uploads succeeded. Both project pages were wrong the moment they
# appeared, and a release description is frozen at upload, so neither could be
# corrected without spending another version.
#
#   A successful upload proves the file arrived.
#   It proves nothing about whether anybody can install and run it.
#
# WHAT IT REFUSES TO ASSUME. That the machine running this has a usable Python
# for installing an application. A modern Python refuses to install one into
# the system environment at all:
#
#   error: externally-managed-environment
#
# That is PEP 668, enforced by Homebrew's Python, Debian's and Ubuntu's. So the
# environment here is created, used and destroyed, which is also the only shape
# that leaves nothing behind: an accumulating pile of throwaway virtual
# environments is how a disk fills up without anybody deciding to fill it.
#
# WHAT IT PROVES. That a person who has never seen this repository can install
# the published version from the public index and get a working tool: the
# version it reports, an installation it says is sound, and a real evaluation
# over packaged evidence producing a real finding.
set -Eeuo pipefail

cd "$(dirname "$0")/.."

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  # Read rather than typed. A gate that took the version from a human is a gate
  # that eventually checks a different version from the one that was released.
  VERSION="$(grep -m1 '^version = ' pyproject.toml | sed -E 's/.*"(.*)".*/\1/')"
fi

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

ENV_DIR=""
cleanup() {
  local rc=$?
  [[ -n "$ENV_DIR" && -d "$ENV_DIR" ]] && rm -rf "$ENV_DIR"
  exit $rc
}
trap cleanup EXIT

step "A clean environment, from nothing"
ENV_DIR="$(mktemp -d)"
python3 -m venv "$ENV_DIR/env"
PIP="$ENV_DIR/env/bin/pip"
CLI="$ENV_DIR/env/bin/m365-governance"
"$PIP" install --quiet --upgrade pip
echo "  ✓ $("$ENV_DIR/env/bin/python" --version)"

step "Install $VERSION from the public index"
# NOT from ./dist, and not with -e. The point is the artefact a stranger gets.
#
# RETRIED, because PyPI accepts an upload long before every edge serves it. The
# first version of this gate failed a release that was already on the index and
# perfectly good, which reports a slow CDN as a broken release -- worse than not
# checking, because it teaches everybody to ignore the check.
INSTALLED=0
for attempt in $(seq 1 10); do
  if "$PIP" install --quiet "m365-governance-as-code==$VERSION" 2>/dev/null; then
    INSTALLED=1
    [[ $attempt -gt 1 ]] && echo "  (served after $attempt attempts)"
    break
  fi
  sleep 30
done
if [[ $INSTALLED -eq 0 ]]; then
  red "  ✗ $VERSION could not be installed from PyPI within five minutes."
  echo "    Either it was never uploaded, or the index has not served it yet."
  echo "    The publish job's own log says which."
  exit 1
fi
echo "  ✓ installed from PyPI"

step "It reports the version that was released"
# The defect this catches was real: 1.0.0b2 was named for one version and
# answered with another, and that value travels into every assessment as
# `engine_version`.
REPORTED="$("$CLI" --version | tr -d '[:space:]')"
if [[ "$REPORTED" != "$VERSION" ]]; then
  red "  ✗ released $VERSION, the installed program reports $REPORTED"
  exit 1
fi
echo "  ✓ $REPORTED"

step "doctor says the installation is sound"
if ! "$CLI" doctor >/dev/null; then
  "$CLI" doctor | sed 's/^/    /'
  red "  ✗ doctor is not happy with a clean installation"
  exit 1
fi
echo "  ✓ doctor healthy"

step "It evaluates packaged evidence and produces a real finding"
# Everything ships inside the package, so this needs no tenant, no checkout and
# no network. A wheel that installs and cannot evaluate has shipped a directory
# of files rather than a tool.
FIXTURES="$("$ENV_DIR/env/bin/python" -c \
  'import m365_governance.resources as r; print(r.packaged("fixtures"))')"
EVIDENCE="$FIXTURES/sharepoint/site-one-owner.json"
[[ -f "$EVIDENCE" ]] || { red "  ✗ packaged fixtures are missing: $EVIDENCE"; exit 1; }

OUT="$("$CLI" evaluate --evidence "$EVIDENCE" --format json)"
echo "$OUT" | "$ENV_DIR/env/bin/python" -c '
import json, sys
run = json.load(sys.stdin)
results = run["results"]
if not results:
    sys.exit("the run carried no results")
decided = [r for r in results if r["outcome"] in ("pass", "fail")]
if not decided:
    sys.exit("nothing was decided: every result was unknown or not-applicable")
print(f"  ✓ {len(results)} results, {len(decided)} decided")
'

step "Every command a reader is given actually runs"
for command in "list-rules" "explain unknown" "validate"; do
  # shellcheck disable=SC2086
  if ! "$CLI" $command >/dev/null 2>&1; then
    red "  ✗ \`m365-governance $command\` fails on a clean installation"
    exit 1
  fi
done
echo "  ✓ list-rules, explain, validate"

step "The contract bundle a consumer vendors is in the wheel"
"$CLI" contracts --out "$ENV_DIR/bundle" >/dev/null
for required in "schemas/collection.schema.json" "csharp/Collection.g.cs" "manifest.json"; do
  [[ -f "$ENV_DIR/bundle/$required" ]] \
    || { red "  ✗ the published wheel does not carry $required"; exit 1; }
done
echo "  ✓ contract published from the installed package"

echo
green "════════════════════════════════════════════════════"
green " $VERSION is installable and works from the public index."
green "════════════════════════════════════════════════════"
