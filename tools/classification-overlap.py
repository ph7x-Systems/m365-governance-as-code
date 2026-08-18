#!/usr/bin/env python3
"""How often the two label rules fire together, over evidence you already have.

    python tools/classification-overlap.py <evidence directory>

WHY THIS IS A TOOL AND NOT A FEATURE. SPO-CLASS-001 and SPO-CLASS-003 both
reported on one site in the first real assessment, which is what duplication
looks like from the outside. They are not duplicates: across the shipped cases
they agree five times and diverge five, they read different facts, and merging
them would force one of them to answer wrongly for a site with a classification
string and no label. That is settled, and it is settled by tests.

What is NOT settled is how often the divergence occurs in practice. One tenant
is a sample of nothing. If `both` dominates everywhere, the two may still be
two correct decisions that deserve to be presented together in a report; if
`only 001` and `only 003` appear materially, the distinction is validated
operationally as well as semantically.

So this counts, and it counts nothing else. It is not telemetry: it reads
evidence already on disk, sends nothing anywhere, and runs when somebody asks
it. It is not a product requirement: no rule, report or contract depends on it,
and deleting it costs the product nothing. It exists so that the question can
be answered the day a second tenant is legitimately available, rather than
argued about from memory.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from m365_governance import engine  # noqa: E402
from m365_governance.loader import load_rule  # noqa: E402
from m365_governance.resources import packaged  # noqa: E402

PAIR = ("SPO-CLASS-001", "SPO-CLASS-003")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("evidence", type=Path, help="a directory of evidence documents")
    args = parser.parse_args()

    if not args.evidence.is_dir():
        print(f"{args.evidence}: not a directory", file=sys.stderr)
        return 2

    rules = [
        load_rule(packaged("rules") / "sharepoint" / f"{name}.yaml").data
        for name in PAIR
    ]

    tally: collections.Counter[str] = collections.Counter()
    decided = 0
    for path in sorted(args.evidence.rglob("*.json")):
        if path.name.startswith("collection-manifest"):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if "classification" not in (document.get("facts") or {}):
            continue
        outcomes = [engine._evaluate(rule, document).outcome.value for rule in rules]
        # Only where both rules reached a verdict about the resource. An
        # `unknown` on either side says something about the collection, and
        # counting it as `neither` would let a permission gap look like a
        # tenant that classifies everything.
        if any(o not in ("pass", "fail", "not-applicable") for o in outcomes):
            tally["not-decided"] += 1
            continue
        decided += 1
        one, three = (o == "fail" for o in outcomes)
        tally[
            "both fire"
            if one and three
            else "only 001"
            if one
            else "only 003"
            if three
            else "neither"
        ] += 1

    if not decided and not tally:
        print("no evidence document carries classification facts", file=sys.stderr)
        return 1

    print(f"{decided} resources where both rules reached a verdict")
    for name in ("both fire", "only 001", "only 003", "neither", "not-decided"):
        if tally[name]:
            share = (
                f"{tally[name] / decided:.0%}"
                if decided and name != "not-decided"
                else ""
            )
            print(f"  {name:12} {tally[name]:5} {share}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
