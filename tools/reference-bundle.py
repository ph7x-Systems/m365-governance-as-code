#!/usr/bin/env python3
"""The artefact a consumer proves it can open.

WHAT THIS IS FOR, AND WHAT IT IS NOT. `consumer` is the one stage of product
path assurance that this engine cannot raise: somebody independent opening the
artefact is the stage a program certifying it would be certifying itself. So
the engine's whole part is to publish an artefact that CAN be proved, with an
identity stable enough for a proof to point at, and then to stop.

This is a COMPATIBILITY ARTEFACT. It is not a fixture -- a fixture is an input
to a test in the repository that owns it, and this is an output that leaves.
It is not tenant evidence: every document in it is fabricated, and the register
says so. It is one thing only: the shape a consumer must be able to read.

WHY IT IS DETERMINISTIC. A proof names a digest. If regenerating produced
different bytes, the digest would change with the machine that ran it, and
every consumer proof would silently stop pointing at anything. So the inputs
are packaged fixtures with fixed timestamps, the assessment time is passed in
rather than read from a clock, and a test regenerates it and compares.

    python tools/reference-bundle.py            rewrite it
    python tools/reference-bundle.py --check    compare, do not write
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from m365_governance import (  # noqa: E402  # noqa: E402
    __version__,
    bundling,
    engine,
    loader,
    registry,
    resources,
)
from m365_governance.results import RunSet  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "m365_governance" / "data" / "reference"

#: The evidence this bundle is built from, named rather than globbed.
#:
#: THE ONE PLACE A LIST IS RIGHT. Everywhere else in this repository an open
#: set is discovered, because the set grows and a list goes stale. This set is
#: closed on purpose: adding a fixture must not silently change the artefact a
#: published consumer proof points at. Changing this list is changing the
#: reference bundle, which is a deliberate act with a new digest behind it.
SOURCES = (
    ("sharepoint", "list-over-limit.json"),
    ("sharepoint", "site-storage-nearly-full.json"),
    ("sharepoint", "site-one-owner.json"),
    ("entra", "entra-conditional-access-everyone-no-exclusion.json"),
)

#: Fixed, because a clock in here is a digest that changes overnight.
CREATED_AT = "2026-01-01T00:00:00Z"


def build(destination: pathlib.Path) -> dict:
    documents = []
    for family, name in SOURCES:
        path = resources.packaged("fixtures") / family / name
        documents.append(json.loads(path.read_text(encoding="utf-8")))

    rules = [r.data for r in loader.load_rules(resources.packaged("rules"))]
    runs = [engine.evaluate(rules, document) for document in documents]
    bundling.write(destination, runs, documents, fmt="markdown")

    every = RunSet(runs=runs)
    (destination / "run-set.json").write_text(
        json.dumps(every.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"runs": len(runs)}


def digest_of(root: pathlib.Path) -> str:
    """The bundle's identity, computed by the bundler that produces bundles.

    NOT A SECOND IMPLEMENTATION. This had its own, and two digest functions
    with slightly different rules give two answers for one artefact -- which
    is the whole failure a digest exists to prevent, arriving through the
    digest itself.
    """
    return bundling.digest_of(root, excluding=("reference.json",))


def describe(root: pathlib.Path, built: dict) -> dict:
    """What a consumer needs to know about what it is holding.

    IT DOES NOT SAY `consumer: proven`, AND IT NEVER WILL. This file is the
    producer's half: what this is, which engine made it, which contracts it
    speaks, and the digest a proof can name. The other half is written by
    whoever opened it, in the proof register, and this engine has no way to
    write it.
    """
    return {
        "reference": "1.0.0",
        "purpose": (
            "the canonical artefact a consumer opens to establish that it can "
            "read what this engine publishes. Not a fixture, not tenant "
            "evidence: every document in it is fabricated"
        ),
        "engine_version": __version__,
        "created_at": CREATED_AT,
        "runs": built["runs"],
        "contracts": {
            name: registry.contract(name) for name in ("run", "run-set", "evidence")
        },
        "digest": digest_of(root),
        "how_a_consumer_proves_it": (
            "open this bundle, read the runs and the run set through the "
            "contracts above, and record consumer, consumer_version, "
            "independence, observed_at and this digest. Deserialising without "
            "an exception proves parsing and not interpretation"
        ),
    }


def main() -> int:
    parsed = argparse.ArgumentParser(description=__doc__)
    parsed.add_argument("--check", action="store_true")
    args = parsed.parse_args()

    staging = pathlib.Path(tempfile.mkdtemp()) / "reference"
    built = build(staging)
    (staging / "reference.json").write_text(
        json.dumps(describe(staging, built), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if args.check:
        if not OUT.exists():
            print("  ✗ no reference bundle on disk", file=sys.stderr)
            return 1
        if digest_of(staging) != digest_of(OUT):
            print(
                "  ✗ the reference bundle on disk is not what this engine "
                "produces. Regenerate it, and know that its digest changed: "
                "every consumer proof naming the old one stops applying.",
                file=sys.stderr,
            )
            return 1
        print(f"  ✓ reference bundle current, {digest_of(OUT)[:23]}...")
        return 0

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(staging, OUT)
    print(f"  {OUT.relative_to(ROOT)}  {digest_of(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
