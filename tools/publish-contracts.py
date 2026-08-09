#!/usr/bin/env python3
"""Assemble the contract bundle a consumer vendors.

    tools/publish-contracts.py --out <dir>

    <dir>/manifest.json     contract version, a digest per schema, one over the set
    <dir>/schemas/*.json    the schemas themselves
    <dir>/csharp/*.g.cs     the generated models

WHY A BUNDLE AND NOT A REFERENCE. A consumer that verified itself against
whatever engine happened to sit at a sibling path would be reproducible only on
the machine where that path exists. On a clean clone, on a build agent, on
somebody else's laptop, the guard silently checks nothing and the build passes
for the wrong reason.

The site already carries that defect in a smaller form, and it is the reason
this exists.

REFRESHING IS AN EXPLICIT OPERATION. Somebody runs this, reads the diff, and
commits it. Nothing compares itself opportunistically, and the consumer can
always say which contract it holds, because it holds it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src" / "m365_governance" / "data" / "schemas"
GENERATED = ROOT / "src" / "m365_governance" / "data" / "generated"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = GENERATED / "manifest.json"
    if not manifest_path.is_file():
        print("  ✗ no manifest — run tools/generate-models.py first")
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # The manifest describes the schemas on disk right now. Publishing a stale
    # one would hand a consumer a digest that matches nothing it received.
    for name, digest in manifest["schemas"].items():
        actual = hashlib.sha256((SCHEMAS / name).read_bytes()).hexdigest()
        if actual != digest:
            print(f"  ✗ {name} has moved since the manifest was written")
            print("    Run tools/generate-models.py, then publish again.")
            return 1

    out = args.out
    for sub in ("schemas", "csharp"):
        target = out / sub
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

    for path in sorted(SCHEMAS.glob("*.json")):
        shutil.copy2(path, out / "schemas" / path.name)
    for path in sorted((GENERATED / "csharp").glob("*.g.cs")):
        shutil.copy2(path, out / "csharp" / path.name)
    shutil.copy2(manifest_path, out / "manifest.json")

    print(
        f"  ✓ contract {manifest['contract_version']} published to {out}: "
        f"{len(manifest['schemas'])} schemas, {len(manifest['generated'])} models"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
