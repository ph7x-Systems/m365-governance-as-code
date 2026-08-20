#!/usr/bin/env bash
#
# THE RELEASE CONTRACT. One command, everything, in order, stopping at the
# first failure.
#
#   ./tools/release-check.sh              everything
#   ./tools/release-check.sh --no-install skip the wheel and clean-install gates
#
# WHY THIS EXISTS. Until now the contract lived in .github/workflows/ci.yml, as
# a list of steps with the reasoning written beside them. That made the file
# excellent documentation and a poor contract: what a developer could prove
# locally was whatever they remembered to type, and what CI proved was
# something else. Two definitions of healthy is one too many.
#
#   If a release gate exists only in GitHub Actions, it does not exist.
#
# CI now prepares an interpreter and runs this. The reasoning that used to live
# in the workflow lives here, next to the command it justifies.
#
# NO SILENT SKIPS. A missing pwsh, a missing build module, a missing virtual
# environment: this stops and says which and how to get it. A partial green
# that looks complete is worse than a red.
set -Eeuo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
INSTALL_GATES=1
[[ "${1:-}" == "--no-install" ]] && INSTALL_GATES=0

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

TMP=""
cleanup() { local rc=$?; [[ -n "$TMP" ]] && rm -rf "$TMP"; exit $rc; }
trap cleanup EXIT

# ── 0. dependencies, all of them, before anything runs ───────────────────────
step "Dependencies"
PY="${PYTHON:-python3}"
MISSING=()
command -v "$PY" >/dev/null || MISSING+=("python3")
"$PY" -c "import m365_governance" 2>/dev/null || MISSING+=("the package: pip install -e .")
for m in ruff pytest coverage jsonschema yaml; do
  "$PY" -c "import $m" 2>/dev/null || MISSING+=("python -m $m: pip install -r requirements-dev.txt")
done
command -v m365-governance >/dev/null || MISSING+=("the console script: pip install -e .")
if [[ $INSTALL_GATES -eq 1 ]]; then
  "$PY" -c "import build" 2>/dev/null || MISSING+=("the build module: pip install build")
  command -v pwsh >/dev/null || MISSING+=("PowerShell: brew install --cask powershell, or apt install powershell")
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
  red "✗ this gate is missing dependencies:"
  printf '    - %s\n' "${MISSING[@]}"
  echo
  echo "  This gate does not skip steps. Install what is missing and run it again."
  echo "  To run the part that does not need them: ./tools/release-check.sh --no-install"
  exit 1
fi
green "  ✓ interpreter, package, dev tools$([[ $INSTALL_GATES -eq 1 ]] && echo ", build, pwsh")"

# ── 1. lint and format ───────────────────────────────────────────────────────
step "ruff check"
ruff check src tools tests

step "ruff format --check"
ruff format --check src tools tests

# ── 1b. the repository language ──────────────────────────────────────────────
# English only. Cheap, and it runs beside the other lint rather than at the end,
# because the cost of finding a whole document in the wrong language after the
# suite has run is the suite having run.
./tools/language-check.sh

# ── 2. every rule, all four layers ───────────────────────────────────────────
# No --rules: the packaged set is what an installed copy uses, so it is what
# gets validated. Passing the checkout's directory here is how the examples
# came to record an absolute local path in a public repository.
step "m365-governance validate"
m365-governance validate

# ── 3. the schemas are themselves valid ──────────────────────────────────────
step "Schemas are valid JSON Schema"
"$PY" - <<'PY'
import json, pathlib
from jsonschema import Draft202012Validator
n = 0
for p in sorted(pathlib.Path("src/m365_governance/data/schemas").glob("*.json")):
    Draft202012Validator.check_schema(json.loads(p.read_text()))
    n += 1
print(f"  ✓ {n} schemas")
PY

# ── 4. the suite, and no skips ───────────────────────────────────────────────
# A skipped test is a test nobody ran. -ra surfaces any; the check below
# refuses them.
step "pytest"
OUT="$(mktemp)"
pytest -q -ra --strict-markers | tee "$OUT"
if grep -qE '[0-9]+ skipped' "$OUT"; then
  rm -f "$OUT"
  red "✗ the suite contains skipped tests"
  exit 1
fi
rm -f "$OUT"

# ── 5. coverage, as a floor rather than a report nobody reads ────────────────
# Measured for the first time at 0.8.0 and found the bounded comparison at 86
# per cent: nearly the whole table published in ARCHITECTURE.md had never
# executed. A documented claim that nothing runs is a claim that drifts.
step "coverage"
coverage run -m pytest -q >/dev/null
coverage report

# ── 6. the examples are current ──────────────────────────────────────────────
# An example in a README is read as a promise. A hand-edited one is a promise
# nobody is keeping: it stays plausible while the behaviour moves underneath.
step "tools/examples.py --check"
"$PY" tools/examples.py --check

# ── 7. every fixture evaluates ───────────────────────────────────────────────
step "Every fixture evaluates"
# Every workload, not one directory. The glob named `sharepoint` and would have
# gone on passing the day a second workload's fixtures arrived, which is the
# kind of green that means nothing was checked. Named rather than globbed: the
# other directories under fixtures hold assessments and comparisons, which are
# not evidence and are not evaluated.
for f in src/m365_governance/data/fixtures/{sharepoint,entra}/*.json; do
  m365-governance evaluate --evidence "$f" --format json > /dev/null
done
echo "  ✓ all fixtures evaluated"

# ── 8. the collector holds no write path ─────────────────────────────────────
# What this proves is narrower than its name. It establishes that the file is
# analysable and that no command in it begins with a mutating verb. It runs
# nothing: a function can parse cleanly, pass this walk, and throw on its first
# line against a tenant. It would also miss a write reached through a variable
# or a REST call. A floor under review, not a substitute for it.
if [[ $INSTALL_GATES -eq 1 ]]; then
  # Every file, not one path. Naming a single script was true while there was
  # a single script, and would have gone on passing — proving nothing about
  # nine tenths of the code — the moment the collector was split into modules.
  step "Collector is read-only"
  pwsh -NoProfile -Command '
    $root = "src/m365_governance/data/collectors"
    $files = Get-ChildItem -Path $root -Recurse -Include *.ps1, *.psm1
    if (-not $files) { Write-Error "no PowerShell found under $root"; exit 1 }
    foreach ($file in $files) {
        $errs = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile(
            $file.FullName, [ref]$null, [ref]$errs)
        if ($errs) {
            $errs | ForEach-Object { Write-Error "$($file.Name): $($_.Message)" }
            exit 1
        }
        $ast = [System.Management.Automation.Language.Parser]::ParseFile(
            $file.FullName, [ref]$null, [ref]$null)
        $names = $ast.FindAll({ param($n)
            $n -is [System.Management.Automation.Language.CommandAst] }, $true) |
                 ForEach-Object { $_.GetCommandName() } | Sort-Object -Unique
        $writes = $names | Where-Object {
            $_ -match "^(Set|New|Remove|Add|Update|Grant|Revoke)-(PnP|Mg|SPO)" }
        if ($writes) {
            Write-Error "write path in $($file.Name): $writes"; exit 1
        }
    }
    Write-Host "  ✓ $($files.Count) files, no write path"'

  # The coverage matrix is derived, never maintained. This is what stops it
  # rotting: a rule, collector, fixture or article added without regenerating
  # fails here rather than leaving a document that quietly says otherwise.
  step "Product coverage matrix is current"
  "$PY" tools/coverage.py --check

  # What can be observed against what is observed. Regenerated so the gap is
  # measured on every release rather than remembered from the last time
  # somebody looked at a cmdlet list.
  # ── DISCOVERY. Every source goes stale, and none of them announces it to a
  # repository. This fails only when something the collector DEPENDS on has
  # disappeared; anything new is a candidate, and a candidate is somebody's
  # decision rather than a broken build.
  step "Nothing this product depends on has moved"
  "$PY" tools/discovery.py --check

  # Staleness only. Whether the output is valid C# is the CONSUMER's gate:
  # it has the compiler, and adding dotnet to this contract would make the
  # engine depend on a toolchain it never uses.
  # RULE 8 AS A GATE. A `nothing remains` claim is established by enumeration
  # and never by fatigue, and as prose it lasted one day. Every card names who
  # unblocks it and what happens next, so that the question "is anything here
  # ours?" is answered by reading rather than by remembering.
  step "Every card in the queue names its authority and its next action"
  "$PY" tools/queue-claim-check.py

  step "The generated models match the schemas"
  "$PY" tools/generate-models.py --check

  step "The observable surface is measured"
  "$PY" tools/surface.py --check

  # Every module loads on its own and exports what it declares. A refactor that
  # leaves a function behind passes every check above and fails here.
  step "Every module imports and exports what it declares"
  pwsh -NoProfile -Command '
    $dir = "src/m365_governance/data/collectors/powershell/sharepoint/modules"
    $exported = @{}
    foreach ($module in (Get-ChildItem "$dir/*.psm1")) {
        try { $loaded = Import-Module $module.FullName -Force -PassThru }
        catch { Write-Error "$($module.Name) does not import: $($_.Exception.Message)"; exit 1 }
        if (-not $loaded.ExportedFunctions.Count) {
            Write-Error "$($module.Name) exports nothing"; exit 1
        }
        foreach ($name in $loaded.ExportedFunctions.Keys) { $exported[$name] = $true }
    }
    $approved = (Get-Verb).Verb
    $unapproved = $exported.Keys | Where-Object { $approved -notcontains ($_ -split "-")[0] }
    if ($unapproved) { Write-Error "unapproved verb: $unapproved"; exit 1 }
    Write-Host "  ✓ $($exported.Count) functions exported, all approved verbs"'

  # The rules nobody remembers. Configured at the repository root so that a
  # suppression is a line in a reviewable file rather than an attribute buried
  # in a function.
  step "PSScriptAnalyzer"
  if (! pwsh -NoProfile -Command 'exit ([int](-not (Get-Module -ListAvailable PSScriptAnalyzer)))'); then
    echo "  PSScriptAnalyzer is not installed."
    echo "  Install-Module PSScriptAnalyzer -Scope CurrentUser"
    exit 1
  fi
  pwsh -NoProfile -Command '
    $found = Invoke-ScriptAnalyzer -Path "src/m365_governance/data/collectors" -Recurse `
        -Settings ./PSScriptAnalyzerSettings.psd1
    if ($found) {
        $found | Format-Table -AutoSize RuleName, Severity, ScriptName, Line, Message
        Write-Error "$($found.Count) findings"; exit 1
    }
    Write-Host "  ✓ clean"'
fi

# ── 9. the wheel, and what it carries ────────────────────────────────────────
# The gate that found the defect it exists to prevent, and the only kind that
# could have. Every other step runs from the repository root, so every other
# step agreed the product worked while `pip install` produced a command-line
# tool with none of its own rules, profiles, schemas or collector.
if [[ $INSTALL_GATES -eq 1 ]]; then
  TMP="$(mktemp -d)"

  step "Build the wheel"
  "$PY" -m build --wheel -o "$TMP/dist" >/dev/null
  ls "$TMP/dist"/*.whl

  step "The wheel carries the product"
  "$PY" - "$TMP" <<'PY'
import collections, glob, pathlib, sys, zipfile
names = zipfile.ZipFile(glob.glob(f"{sys.argv[1]}/dist/*.whl")[0]).namelist()
found = collections.Counter(
    n.split("/")[2] for n in names
    if n.startswith("m365_governance/data/") and n.count("/") > 2)
missing = [d for d in ("rules", "profiles", "schemas", "collectors", "fixtures")
           if not found.get(d)]
print("  " + str(dict(found)))
if missing:
    sys.exit(f"  ✗ the wheel is missing {missing}: the package does not contain the product")

# Counting directories is not enough. A glob that named only *.ps1 left every
# .psm1 out, and the count above still said `collectors: 1` while the collector
# could not import a single one of its own modules. Compare against the tree.
data = pathlib.Path("src/m365_governance/data")
on_disk = {str(p.relative_to(data.parent.parent))
           for p in (data / "collectors").rglob("*")
           if p.suffix in {".ps1", ".psm1"}}
absent = sorted(on_disk - set(names))
if absent:
    sys.exit(f"  ✗ PowerShell files not carried by the wheel: {absent}")
PY

  # ── 10. a clean installation is the reference environment ──────────────────
  # `cd` out of the checkout is the whole point. Run from the repository and
  # these steps prove nothing at all.
  step "Install into an empty environment and run from outside any checkout"
  "$PY" -m venv "$TMP/env"
  "$TMP/env/bin/pip" install --quiet "$TMP"/dist/*.whl
  mkdir -p "$TMP/empty"
  (
    cd "$TMP/empty"
    G="$TMP/env/bin/m365-governance"
    "$G" doctor > doctor.txt
    "$G" list-rules > /dev/null
    "$G" validate > /dev/null
    FIXTURE=$("$TMP/env/bin/python" -c \
      'from m365_governance.resources import packaged; print(packaged("fixtures")/"sharepoint"/"list-over-limit.json")')
    "$G" evaluate --evidence "$FIXTURE" --format json > /dev/null
    "$G" collect sites --dry-run --tenant-url https://x-admin.sharepoint.com \
      --client-id 00000000-0000-0000-0000-000000000000 --output out.json > /dev/null

    # ── 11. nothing reaches back into the checkout ──────────────────────────
    if grep -q "$ROOT" doctor.txt; then
      red "  ✗ the installed product resolves a path inside the checkout"
      cat doctor.txt
      exit 1
    fi
    echo "  ✓ the product runs from outside, and every path stays inside the installation"
  )
fi

echo
green "════════════════════════════════════════════════════"
green " m365-governance passes the release contract."
green "════════════════════════════════════════════════════"
[[ $INSTALL_GATES -eq 1 ]] || red " (without the wheel and clean-install gates, which were skipped)"
