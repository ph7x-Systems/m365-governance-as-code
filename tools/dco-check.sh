#!/usr/bin/env bash
# Every commit in a range carries a Developer Certificate of Origin sign-off.
#
#   ./tools/dco-check.sh <base> [head]
#
# WHY A SCRIPT AND NOT TEN LINES OF YAML. A contributor cannot run a workflow.
# A rule they can only discover by pushing and being refused is a rule that
# wastes their afternoon, and CI running something nobody can reproduce locally
# is the same defect this repository removes everywhere else.
#
# WHAT IT REFUSES, AND WHY EACH ONE MATTERS.
#
#   no sign-off          the certificate was never made
#   somebody else's      a sign-off by a person who did not write the commit is
#                        a certificate about work the signer did not do
#
# It names the commits. "DCO check failed" with nothing behind it is the
# message this project exists to stop shipping.
set -euo pipefail

BASE="${1:?usage: dco-check.sh <base> [head]}"
HEAD="${2:-HEAD}"

missing=0
while read -r sha; do
  [ -z "$sha" ] && continue
  author="$(git show -s --format='%an <%ae>' "$sha")"
  body="$(git show -s --format='%B' "$sha")"

  if ! grep -qiE "^Signed-off-by: .+ <.+@.+>$" <<< "$body"; then
    echo "  ✗ $(git show -s --format='%h %s' "$sha")"
    echo "    no Signed-off-by. Add one with: git commit -s --amend"
    missing=1
  elif ! grep -qiF "Signed-off-by: $author" <<< "$body"; then
    echo "  ✗ $(git show -s --format='%h %s' "$sha")"
    echo "    signed off by someone other than the author ($author)"
    missing=1
  fi
done < <(git rev-list "$BASE".."$HEAD")

if [ "$missing" -ne 0 ]; then
  echo
  echo "See DCO.txt. Sign a whole branch off with:"
  echo "  git rebase --signoff $BASE"
  exit 1
fi
echo "  ✓ every commit is signed off by its author"
