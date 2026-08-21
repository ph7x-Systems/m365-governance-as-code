#!/usr/bin/env python3
"""Assemble the contract bundle a consumer vendors.

    tools/publish-contracts.py --out <dir>

    <dir>/manifest.json     contract version, a digest per schema, one over the set
    <dir>/schemas/*.json    the schemas themselves
    <dir>/csharp/*.g.cs     the generated models
    <dir>/samples/*.json    runs this engine really emitted
    <dir>/assessments/*.json  whole assessments, digests and all
    <dir>/comparisons/*.json  what changed between two of them

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
    for sub in ("schemas", "csharp", "samples", "assessments", "comparisons"):
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

    # The fixture registry travels with the bundle: the samples below are
    # produced from fixtures, and `may_be_presented_as_tenant_observation`
    # is the field a consumer reads to keep a construction from being shown
    # as a tenant reading. A consumer vendored this file by hand first;
    # a bundle that omitted it failed the consumer's drift gate, correctly.
    shutil.copy2(
        ROOT / "src" / "m365_governance" / "data" / "fixture-registry.json",
        out / "fixture-registry.json",
    )

    # Real output, not hand-written examples. Every fixture that evaluates
    # becomes a sample, so the consumer exercises the contract against what the
    # engine actually produces.
    #
    # EVERY FAMILY, NOT ONE OF THEM. This globbed `fixtures/sharepoint` alone,
    # written when that was the only family there was. A licensing family
    # arrived with three fixtures and a consumer received none of them: the
    # bundle looked healthy because seventy-one SharePoint samples were in it,
    # and the new family was invisible to everything downstream. The archive
    # directory is skipped because its documents are of superseded contracts
    # and are exercised elsewhere.
    #
    # NAMED, SO THAT ADDING ONE IS DELIBERATE. Globbing every family picked up
    # the migration fixtures, which are lists of documents rather than evidence
    # and which `evaluate` refuses, correctly. A skip would have hidden that;
    # the list below is the honest version, and a family missing from it is a
    # family the consumer never receives.
    root = ROOT / "src" / "m365_governance" / "data" / "fixtures"
    families = ("sharepoint", "licensing")
    fixtures = sorted(f for family in families for f in (root / family).glob("*.json"))
    written = 0
    for fixture in fixtures:
        # THROUGH THIS INTERPRETER, NEVER THROUGH THE PATH. `m365-governance`
        # resolves to whatever engine happens to be installed on the machine,
        # which is how a bundle came to carry samples produced by one engine and
        # schemas published by another -- the exact disagreement the rest of
        # this file exists to prevent. It also resolved to nothing at all here,
        # and the loop below said so by writing no samples.
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "m365_governance.cli",
                "evaluate",
                "--evidence",
                str(fixture),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        # A SKIPPED FIXTURE IS A FAILED PUBLISH. Continuing quietly meant the
        # count at the bottom was the only witness, and it only spoke when the
        # number reached zero; a bundle short of three samples shipped.
        if done.returncode != 0:
            print(f"  ✗ {fixture.name} could not be evaluated")
            print("   ", (done.stderr or done.stdout).strip().splitlines()[-1])
            return 1
        (out / "samples" / f"run-{fixture.stem}.json").write_text(
            done.stdout, encoding="utf-8"
        )
        written += 1
    # What this engine can do, as bytes rather than as a description of bytes.
    # A consumer projecting the capabilities -- a public page per collector, per
    # rule, a coverage matrix -- needs the document itself, and generating it
    # locally would mean running an engine it may not have. It is derived on
    # every publish, so it cannot be stale by the time it arrives.
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "m365_governance.cli",
            "capabilities",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        print("  ✗ the capability manifest could not be produced")
        return 1
    (out / "capabilities.json").write_text(done.stdout, encoding="utf-8")

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

    # A comparison is the one document that relates two others, so a consumer
    # that never received one cannot have exercised how two archives are read
    # together.
    comparisons = sorted(
        (ROOT / "src" / "m365_governance" / "data" / "fixtures" / "comparison").glob(
            "*.json"
        )
    )
    if not comparisons:
        print("  ✗ no comparison fixtures to publish")
        return 1
    for path in comparisons:
        shutil.copy2(path, out / "comparisons" / f"comparison-{path.name}")

    if written < 20:
        print(f"  ✗ only {written} samples produced, which is fewer than this")
        print("    engine has fixtures. A bundle with almost no samples lets a")
        print("    consumer pass by exercising nothing.")
        return 1

    print(
        f"  ✓ contract {manifest['contract_version']} published to {out}: "
        f"{len(manifest['schemas'])} schemas, {len(manifest['generated'])} models, "
        f"{written} samples, {len(assessments)} assessments, "
        f"{len(comparisons)} comparisons"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
