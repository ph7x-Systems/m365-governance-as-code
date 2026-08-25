#!/usr/bin/env bash
#
# Build the engine as a standalone directory that runs without a Python
# installation.
#
# WHY THIS EXISTS. The engine and the desktop consumer are one product
# delivered as two binaries, and they have to agree on a contract. A consumer
# that resolves whatever `m365-governance` happens to be on PATH is a product
# whose behaviour is decided by an unrelated installation, and the observed
# result was a consumer with an empty catalogue: the released engine published
# an older contract, every rule surface emptied, and the application presented
# as a configured tenant containing no rules.
#
# So a consumer carries a matched engine, and this produces the thing it
# carries. The wheel on PyPI remains how somebody installs the command line for
# themselves; this is not a second distribution of the product, it is the same
# build made resolvable by something that ships it.
#
# ONE FOLDER, NOT ONE FILE. PyInstaller's one-file mode unpacks into a
# temporary directory on every run, which costs start-up time, leaves those
# directories behind when a run crashes, and puts the executable somewhere
# different from where it was signed. A consumer embeds this in its own
# package, so nobody browses the folder and none of that is worth paying for.
#
# METADATA IS COLLECTED DELIBERATELY. Without it the build runs, reports its
# own version as `0.0.0+unknown`, and `doctor` fails PyYAML as unusable while
# PyYAML works — an engine that cannot say which engine it is. `doctor` caught
# exactly that on the first build here, which is the check doing its job.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

python="${PYTHON:-$root/.venv/bin/python}"
[[ -x "$python" ]] || { echo "no interpreter at $python. Set PYTHON." >&2; exit 1; }

"$python" -c "import PyInstaller" 2>/dev/null || {
    echo "PyInstaller is not installed in $python." >&2
    echo "Install this project's packaging extra:  $python -m pip install -e '.[packaging]'" >&2
    exit 1
}

out="$root/build/standalone"
mkdir -p "$out"

# The console script's entry point, called the way the installed command calls
# it. Naming `cli:main` here rather than pointing PyInstaller at a module keeps
# one definition of what running this engine means.
cat > "$out/entry.py" <<'PY'
from m365_governance.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
PY

"$python" -m PyInstaller \
    --name m365-governance \
    --onedir --noconfirm --clean --console \
    --distpath "$out/dist" --workpath "$out/work" --specpath "$out" \
    --collect-data m365_governance \
    --collect-submodules m365_governance \
    --copy-metadata m365-governance-as-code \
    --copy-metadata PyYAML \
    --copy-metadata jsonschema \
    "$out/entry.py"

engine="$out/dist/m365-governance/m365-governance"

# THE BUILD IS NOT FINISHED UNTIL IT HAS ANSWERED. A directory that exists
# proves nothing: the first build here produced one that ran, and could not
# find its own package metadata. Every check below failed on it.
echo
echo "checking the build answers for itself"
"$engine" --version
"$engine" capabilities --format json > "$out/capabilities.json"
"$python" - "$out/capabilities.json" <<'PY'
import json, sys

manifest = json.load(open(sys.argv[1]))
schema, rules = manifest["$schema"], manifest["rules"]
print(f"  {schema}")
print(f"  {len(rules)} rules")
if not rules:
    raise SystemExit("the standalone build publishes no rules: its data was not collected")
PY
"$engine" doctor > "$out/doctor.txt" 2>&1 || {
    echo "doctor reports this build is not usable:" >&2
    cat "$out/doctor.txt" >&2
    exit 1
}
echo "  doctor: no problems"
echo
echo "standalone engine at $out/dist/m365-governance"
