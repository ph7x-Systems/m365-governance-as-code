#!/usr/bin/env python3
"""What is true of every rule, one rule at a time.

WHY THIS EXISTS. The catalogue is about to grow, and a catalogue grows in the
direction of whatever nobody measures. `tools/coverage.py` answers *how much of
Microsoft 365 does this reach*, by domain. Nothing answered *is this rule
finished*, and "we have fifty rules" is a sentence anybody can say about fifty
checks that cite nothing and have never been observed reaching an answer.

TWO GATES AND ONE STATE.

    RULE-READY      the rule is finished as a rule: it says what it checks, on
                    whose authority, from which evidence, what a pass does not
                    settle, a collector feeds it, and it has been SEEN reaching
                    pass, fail and unknown against the packaged fixtures.

    TENANT-PROVEN   a real tenant produced the evidence it decides from, that
                    evidence was written down, and an assessment was made of
                    it. A rule that has never met a tenant has been tested
                    against what we imagined Microsoft 365 returns.

    PRODUCT-PATH    that assessment crossed the bundle and a consumer read it.
                    Reported, never enforced: it depends on work outside the
                    rule.

Declared behaviour and observed behaviour are different claims, and this
product exists because somebody conflated them. An `unknown` message written
and never reached is an untested branch on the path that matters most.

NO RULE PASSES WITHOUT HAVING BEEN RUN AGAINST A TENANT. There is no exception
list, and there was one for about an hour: seventeen rules predated the rule,
so I wrote their names down with a reason each and the gate went green. That is
how an absolute becomes a tolerance, and the register would have been the place
every future rule went to wait.

The gate is red instead, and the red names the seventeen. A rule proved against
imagined evidence is a rule proved against nothing, and the debt closes by
running them, never by writing them down.

    python3 tools/rule-readiness.py            report, and fail on a rule that
                                               is not ready
    python3 tools/rule-readiness.py --check    also fail when the published
                                               table on disk differs
    python3 tools/rule-readiness.py --json     the table, for a consumer

WHAT IT DOES NOT DO. It does not judge whether a rule is worth having, and it
cannot: that is a question about Microsoft 365 and about who is asking. It
judges whether a rule that exists is finished.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import capabilities, engine, loader  # noqa: E402

RULES = ROOT / "src" / "m365_governance" / "data" / "rules"
FIXTURES = ROOT / "src" / "m365_governance" / "data" / "fixtures"
PUBLISHED = ROOT / "docs" / "RULE-READINESS.json"

#: The outcomes a rule must have been seen reaching. `not_applicable` and
#: `invalid_evidence` are deliberately absent: the first depends on the corpus
#: happening to hold another resource type, and the second needs a document
#: that is wrong on purpose, which belongs to the schema tests rather than to
#: the catalogue.
OBSERVED = ("pass", "fail", "unknown")

def fixtures() -> list[dict]:
    """Every packaged evidence document, and only those.

    `archive/` holds documents in retired schema versions, kept so a reader can
    see what a contract looked like; evaluating against them would report a
    rule as unfinished because a shape from two versions ago cannot decide it.

    The folder also holds canonical assessments, comparisons and coverage
    documents, which are fixtures of other parts of the product. Handed to the
    evaluator they do not produce a wrong verdict: they crash, because they
    carry no resource to identify.
    """
    corpus = []
    for path in sorted(FIXTURES.rglob("*.json")):
        if "archive" in path.parts:
            continue
        document = loader.load_evidence(path).data
        resource = document.get("resource")
        if isinstance(resource, dict) and "workload" in resource:
            corpus.append(document)
    return corpus


def observed(authored: list[dict], corpus: list[dict]) -> dict[str, set[str]]:
    """Which outcomes each rule has actually been seen reaching."""
    seen: dict[str, set[str]] = {rule["id"]: set() for rule in authored}
    for document in corpus:
        for rule in authored:
            seen[rule["id"]].add(engine.evaluate_rule(rule, document).outcome.name.lower())
    return seen


def feeds(manifest: dict) -> dict[str, list[str]]:
    """Which capabilities produce the evidence each rule decides from.

    Derived, never declared on the rule: a rule naming its own collector would
    be a second place for that fact to be wrong.
    """
    out: dict[str, list[str]] = {}
    for capability in manifest["capabilities"]:
        for rule_id in capability.get("consumed_by", []):
            out.setdefault(rule_id, []).append(capability["name"])
    return out


def readiness(rule: dict, seen: set[str], caps: list[str], manifest: dict) -> dict:
    basis = rule.get("basis", {})
    limits = rule.get("limitations", {})
    outcomes = rule.get("outcomes", {})
    rule_id = rule["id"]

    checks = {
        "basis_explicit": bool(basis.get("type")),
        "source_cited": bool(basis.get("sources"))
        or basis.get("type") in {"convention", "opinion"},
        "evidence_declared": bool(rule.get("evidence_requirements")),
        "unknown_documented": bool(outcomes.get("unknown", {}).get("message")),
        "pass_boundary": bool(limits.get("passes_without_resolving")),
        "collector_exists": bool(caps),
    }
    for outcome in OBSERVED:
        checks[f"observed_{outcome}"] = outcome in seen

    by_name = {c["name"]: c for c in manifest["capabilities"]}
    stages = [by_name[c]["collector"]["proof"]["stages"] for c in caps if c in by_name]
    tenant = any(
        s.get("acquisition") == "proven"
        and s.get("evidence") == "proven"
        and s.get("assessment") == "proven"
        for s in stages
    )
    product_path = any(
        s.get("bundle") == "proven" and s.get("consumer") == "proven" for s in stages
    )

    return {
        "id": rule_id,
        "service": rule.get("service", ""),
        "basis": basis.get("type", ""),
        "capabilities": caps,
        "checks": checks,
        "rule_ready": all(checks.values()),
        "tenant_proven": tenant,
        "product_path": product_path,
    }


def build() -> dict:
    authored = [r.data for r in loader.load_rules(RULES)]
    manifest = capabilities.manifest(RULES)
    seen = observed(authored, fixtures())
    feeding = feeds(manifest)

    lines = [
        readiness(rule, seen[rule["id"]], feeding.get(rule["id"], []), manifest)
        for rule in sorted(authored, key=lambda r: r["id"])
    ]
    return {
        "_readme": (
            "Generated by tools/rule-readiness.py. RULE-READY and TENANT-PROVEN "
            "are gates and fail the build. There is no exception list: a rule "
            "that has never been run against a tenant fails. PRODUCT-PATH is "
            "reported and never enforced, because it depends on work outside "
            "the rule."
        ),
        "rules": len(lines),
        "rule_ready": sum(1 for r in lines if r["rule_ready"]),
        "collectable": sum(1 for r in lines if r["checks"]["collector_exists"]),
        "tenant_proven": sum(1 for r in lines if r["tenant_proven"]),
        "product_path": sum(1 for r in lines if r["product_path"]),
        "by_service": dict(sorted(Counter(r["service"] for r in lines).items())),
        "detail": lines,
    }


def unproven(table: dict) -> list[dict]:
    """Rules that have never been run against a tenant."""
    return [r for r in table["detail"] if not r["tenant_proven"]]


def as_text(table: dict) -> str:
    lines = [
        f"{table['rules']} rules",
        f"{table['collectable']} collectable",
        f"{table['tenant_proven']} tenant-proven",
        f"{table['product_path']} product-path proven",
        "",
        "  " + " · ".join(f"{n} {s}" for s, n in table["by_service"].items()),
    ]
    unfinished = [r for r in table["detail"] if not r["rule_ready"]]
    if unfinished:
        lines += ["", f"  NOT RULE-READY: {len(unfinished)}"]
        for rule in unfinished:
            absent = [k for k, v in rule["checks"].items() if not v]
            lines.append(f"    {rule['id']:<20} {', '.join(absent)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="also fail when docs/RULE-READINESS.json differs")
    parser.add_argument("--json", action="store_true", help="print the table")
    args = parser.parse_args()

    table = build()
    if args.json:
        print(json.dumps(table, indent=1))
        return 0

    print(as_text(table))
    failed = False

    if args.check:
        current = json.dumps(table, indent=1, ensure_ascii=False) + "\n"
        if not PUBLISHED.exists() or PUBLISHED.read_text(encoding="utf-8") != current:
            print("\n  ✗ docs/RULE-READINESS.json is stale: run the generator")
            failed = True
    else:
        PUBLISHED.parent.mkdir(parents=True, exist_ok=True)
        PUBLISHED.write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    if table["rule_ready"] != table["rules"]:
        print(f"\n  ✗ {table['rules'] - table['rule_ready']} rules are not RULE-READY")
        failed = True

    new = unproven(table)
    if new:
        print(f"\n  ✗ {len(new)} rules have never been run against a tenant. "
              "No rule passes without that.")
        for rule in new:
            caps = ", ".join(rule["capabilities"]) or "no collector"
            print(f"      {rule['id']:<20} {caps}")
        failed = True

    if not failed:
        print("\n  ✓ every rule is RULE-READY and has been run against a tenant")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
