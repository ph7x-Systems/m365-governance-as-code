#!/usr/bin/env bash
# The repository language is English. This catches the obvious regressions.
#
# WHAT IT LOOKS AT: technical and operational files -- code, tests, tools,
# schemas, documentation, and the commit messages a branch adds. Not localized
# content and not verbatim external evidence, which are the two exceptions the
# contract allows: a guard that flags legitimate localization is a guard people
# learn to skip, and a skipped guard is worse than no guard.
#
# WHAT IT CANNOT DO: judge prose. It matches function words that are common in
# Portuguese and rare-to-absent in English technical writing, which catches a
# paragraph and will not catch a single mistranslated noun. That is the right
# trade: the failure it exists to stop is somebody writing a whole comment,
# document or commit message in the wrong language.

set -euo pipefail
cd "$(dirname "$0")/.."

# Whole words only, and chosen for being unambiguous. Words that are also
# English (`a`, `no`, `os`, `use`, `data`) are deliberately absent: one false
# positive on a legitimate file costs more than the regression it would catch.
WORDS='\b(não|nao|porque|também|tambem|ficheiro|ficheiros|nenhum|nenhuma|qualquer|sempre|nunca|precisa|apenas|através|atraves|própria|propria|mesmo|quando|onde|assim|ainda|então|entao|antes|depois|sobre|entre|cada|todos|todas|foram|estão|estao|isso|aquilo|deve|pode|fazer|escrever|guardar|recolha|regra|regras|fatia|fatias)\b'

fail=0

report() {
  fail=1
  printf '  %s\n' "$1"
}

echo "▸ Repository language"

# Tracked technical and operational files. Localized content lives nowhere in
# this repository today; when it does, exclude its directory here and say why.
while IFS= read -r path; do
  case "$path" in
    *.py|*.ps1|*.psm1|*.sh|*.md|*.json|*.yaml|*.yml|*.cs|*.toml) ;;
    *) continue ;;
  esac
  # Verbatim external evidence: a vendor's own message, quoted to stay proof.
  # Fixtures record what a system returned and are read, not written, here.
  case "$path" in
    src/m365_governance/data/fixtures/*) continue ;;
  esac
  if hits=$(grep -inE "$WORDS" "$path" | head -3) && [ -n "$hits" ]; then
    report "$path"
    printf '%s\n' "$hits" | sed 's/^/      /'
  fi
done < <(git ls-files)

# The commit messages this branch adds. Published history stays as it is, so
# only what is not yet on the main branch is checked.
base="${1:-origin/main}"
if git rev-parse --verify --quiet "$base" >/dev/null; then
  while IFS= read -r commit; do
    if git log -1 --format='%B' "$commit" | grep -qiE "$WORDS"; then
      report "commit $(git log -1 --format='%h %s' "$commit")"
    fi
  done < <(git rev-list "$base..HEAD")
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "  The repository language is English. Localized product content and"
  echo "  verbatim external evidence are the only exceptions, and neither is"
  echo "  what the lines above are."
  exit 1
fi

echo "  ✓ English"
