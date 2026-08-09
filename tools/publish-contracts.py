#!/usr/bin/env python3
"""Assemble the contract bundle a consumer vendors.

    tools/publish-contracts.py --out <dir>

    <dir>/manifest.json     contract version, a digest per schema, one over the set
    <dir>/schemas/*.json    the schemas themselves
    <dir>/csharp/*.g.cs     the generated models
    <dir>/samples/*.json    runs this engine really emitted
    <dir>/assessments/*.json  whole assessments, digests and all

WHY SAMPLES TRAVEL WITH IT. A contract a consumer cannot exercise is a contract
it can only agree with in principle. The samples are produced by evaluating
this engine's own fixtures, so the consumer validates and deserialises the same
bytes the engine emits rather than examples somebody wrote by hand.

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
import subprocess
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
    for uri, entry in manifest["schemas"].items():
        source = ROOT / "src" / "m365_governance" / "data" / entry["path"]
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != entry["digest"]:
            print(f"  ✗ {uri} has moved since the manifest was written")
            print("    Run tools/generate-models.py, then publish again.")
            return 1

    out = args.out
    for sub in ("schemas", "csharp", "samples", "assessments"):
        target = out / sub
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

    for path in sorted(SCHEMAS.rglob("*.json")):
        target = out / "schemas" / path.relative_to(SCHEMAS)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for path in sorted((GENERATED / "csharp").glob("*.g.cs")):
        shutil.copy2(path, out / "csharp" / path.name)
    shutil.copy2(manifest_path, out / "manifest.json")

    # Real output, not hand-written examples. Every fixture that evaluates
    # becomes a sample, so the consumer exercises the contract against what the
    # engine actually produces.
    fixtures = sorted(
        (ROOT / "src" / "m365_governance" / "data" / "fixtures" / "sharepoint").glob(
            "*.json"
        )
    )
    written = 0
    for fixture in fixtures:
        done = subprocess.run(
            [
                "m365-governance",
                "evaluate",
                "--evidence",
                str(fixture),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if done.returncode != 0:
            continue
        (out / "samples" / f"run-{fixture.stem}.json").write_text(
            done.stdout, encoding="utf-8"
        )
        written += 1
    # An assessment is the only artefact whose identity is derived from its own
    # bytes, so a consumer that never received one cannot have tested the part
    # of the contract that matters most. This one used to be copied across by
    # hand, which held until the first schema change and then quietly held a
    # document whose digests described an older engine.
    assessments = sorted(
        (ROOT / "src" / "m365_governance" / "data" / "fixtures" / "assessment").glob(
            "*.json"
        )
    )
    if not assessments:
        print("  ✗ no assessment fixtures to publish")
        return 1
    for path in assessments:
        shutil.copy2(path, out / "assessments" / f"assessment-{path.name}")

    if written < 20:
        print(f"  ✗ only {written} samples produced, which is fewer than this")
        print("    engine has fixtures. A bundle with almost no samples lets a")
        print("    consumer pass by exercising nothing.")
        return 1

    print(
        f"  ✓ contract {manifest['contract_version']} published to {out}: "
        f"{len(manifest['schemas'])} schemas, {len(manifest['generated'])} models, "
        f"{written} samples, {len(assessments)} assessments"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
