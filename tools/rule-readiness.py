#!/usr/bin/env python3
"""What is true of every rule, one rule at a time.

WHY THIS EXISTS. The catalogue is about to grow, and a catalogue grows in the
direction of whatever nobody measures. `tools/coverage.py` answers *how much of
Microsoft 365 does this reach*, by domain. Nothing answered *is this rule
finished*, and "we have fifty rules" is a sentence anybody can say about fifty
checks that cite nothing and have never been observed reaching an answer.

TWO GATES AND ONE STATE.

    RULE-READY      the rule is finished as a rule. Sixteen conditions, and
                    none of them is a matter of taste: what it checks, on whose
                    authority and from which source, which service and
                    capability, which endpoint and API version, with which
                    permission, from which declared evidence, what a pass does
                    not settle, that unknown cannot become a pass, that nothing
                    it needs is written rather than read -- and that it has been
                    SEEN reaching pass, fail, unknown and a refused read.

                    THE FACTS ABOUT ACQUISITION ARE DERIVED, NEVER TYPED. A rule
                    naming its own endpoint, version or permission would be a
                    second place for those to be wrong; they come from the
                    capability manifest, which comes from the collector.

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
import re
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


def families(rule: dict) -> set[str]:
    """The fact families a rule reads, from the paths it declares.

    `authorization_policy.guest_role_template_id` belongs to
    `authorization_policy`, which is the name coverage uses when it says an
    area was requested and came back unavailable."""
    return {
        str(f.get("path", "")).split(".")[0]
        for f in rule.get("evidence_requirements", [])
        if f.get("path")
    }


def observed(
    authored: list[dict], corpus: list[dict]
) -> tuple[dict[str, set[str]], dict[str, bool]]:
    """Which outcomes each rule has been seen reaching, and whether it has ever
    met a refusal.

    A refusal is not a missing fact. It reaches a rule as `unknown` like any
    other absence, and what distinguishes it is the coverage block: the area
    was asked for and the tenant said no. A rule that has only ever met silence
    has never been shown the answer a real tenant gives first."""
    seen: dict[str, set[str]] = {rule["id"]: set() for rule in authored}
    refused: dict[str, bool] = {rule["id"]: False for rule in authored}
    for document in corpus:
        unavailable = set((document.get("coverage") or {}).get("unavailable") or {})
        for rule in authored:
            outcome = engine.evaluate_rule(rule, document).outcome.name.lower()
            seen[rule["id"]].add(outcome)
            if outcome == "unknown" and families(rule) & unavailable:
                refused[rule["id"]] = True
    return seen, refused


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


def endpoints(caps: list[str], by_name: dict) -> list[tuple[str, str]]:
    """Every surface a rule rests on, with the kind of thing it is.

    A Graph collector reads `GET /v1.0/...` and a PowerShell collector reads a
    cmdlet. Asking the second for an API version in its path was this gate
    measuring one shape and finding the other missing, which is the defect it
    exists to catch, aimed at itself."""
    return [
        (by_name[c]["collector"]["kind"], read)
        for c in caps if c in by_name
        for read in by_name[c]["collector"]["reads"]
    ]


def permissions(caps: list[str], by_name: dict) -> list[str]:
    """The least privilege each surface needs, as the collector records it.

    `not-established` is kept rather than filtered. It is a recorded answer:
    the manifest's own comment says least privilege is written where a source
    establishes it and invented nowhere, and a gate that demanded a scope here
    would be asking somebody to make one up."""
    return [p for c in caps if c in by_name for p in by_name[c]["collector"]["permissions"]]


def readiness(rule: dict, seen: set[str], caps: list[str], manifest: dict,
              refused: bool = False) -> dict:
    basis = rule.get("basis", {})
    limits = rule.get("limitations", {})
    outcomes = rule.get("outcomes", {})
    evidence = rule.get("evidence_requirements", [])

    by_name = {c["name"]: c for c in manifest["capabilities"]}
    reads = endpoints(caps, by_name)
    scopes = permissions(caps, by_name)
    stages = [by_name[c]["collector"]["proof"]["stages"] for c in caps if c in by_name]
    states = [by_name[c]["collector"]["live_validation_state"] for c in caps if c in by_name]

    checks = {
        # ── what the rule says of itself ──────────────────────────────────
        "basis_explicit": bool(basis.get("type")),
        "source_cited": bool(basis.get("sources"))
        or basis.get("type") in {"convention", "opinion"},
        "service_named": bool(rule.get("service")),
        "evidence_declared": bool(evidence),
        "unknown_documented": bool(outcomes.get("unknown", {}).get("message")),
        "pass_boundary": bool(limits.get("passes_without_resolving")),
        # An optional requirement would let a rule decide without the fact it
        # names, which is how `unknown` quietly becomes `pass`. The schema
        # already refuses it; this says so where the ladder is read.
        "unknown_cannot_pass": all(f.get("required") for f in evidence),

        # ── what the acquisition path says, derived from the manifest ─────
        "capability_known": bool(caps),
        "endpoint_named": bool(reads),
        # A Graph surface names its version in the path; a cmdlet has no
        # version to name, and the module it belongs to is the collector's
        # fact rather than the rule's.
        "api_version_named": bool(reads) and all(
            re.search(r"/(v1\.0|beta)/", read) for kind, read in reads if kind == "graph"
        ),
        # DECLARED, not necessarily known. An empty list is an omission; a list
        # saying `not-established` is an answer, and the count of rules resting
        # on one is published below rather than hidden by passing.
        "permission_declared": bool(scopes),
        # READ ONLY IS A CONSTRUCTION PROPERTY, not a promise in prose. Every
        # surface a rule rests on is fetched, and a collector that ever needed
        # a write would show up here rather than in a paragraph nobody runs.
        "no_write_path": bool(reads) and all(
            read.strip().startswith("GET") if kind == "graph"
            else read.strip().startswith(("Get-", "Test-", "Measure-", "Export-"))
            for kind, read in reads
        ),
        "acquisition_declared": bool(states) and all(
            s in {"none", "negative-only", "provider-only", "partial", "full"} for s in states
        ),
    }
    for outcome in OBSERVED:
        checks[f"observed_{outcome}"] = outcome in seen
    # A REFUSED READ IS NOT A MISSING FACT. One is the tenant saying no and the
    # other is nobody having asked, and a rule that has never met a refusal has
    # an untested branch on the path a real tenant reaches first.
    #
    # There is no `refused` outcome and there should not be: a refusal reaches a
    # rule as `unknown`, and what distinguishes it is the coverage block saying
    # the area was requested and came back unavailable. This gate asked for an
    # outcome that does not exist, which is why every rule failed it.
    checks["observed_refusal"] = refused

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
        "id": rule["id"],
        "service": rule.get("service", ""),
        "basis": basis.get("type", ""),
        "capabilities": caps,
        "endpoints": [read for _, read in reads],
        "permissions": sorted(set(scopes)),
        "permission_established": bool(scopes) and "not-established" not in scopes,
        "checks": checks,
        "rule_ready": all(checks.values()),
        "tenant_proven": tenant,
        "product_path": product_path,
    }


def build() -> dict:
    authored = [r.data for r in loader.load_rules(RULES)]
    manifest = capabilities.manifest(RULES)
    seen, refused = observed(authored, fixtures())
    feeding = feeds(manifest)

    lines = [
        readiness(rule, seen[rule["id"]], feeding.get(rule["id"], []), manifest,
                  refused[rule["id"]])
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
        "collectable": sum(1 for r in lines if r["checks"]["capability_known"]),
        "least_privilege_established": sum(1 for r in lines if r["permission_established"]),
        "tenant_proven": sum(1 for r in lines if r["tenant_proven"]),
        "product_path": sum(1 for r in lines if r["product_path"]),
        "by_service": dict(sorted(Counter(r["service"] for r in lines).items())),
        "detail": lines,
    }


def unproven(table: dict) -> list[dict]:
    """Rules that have never been run against a tenant."""
    return [r for r in table["detail"] if not r["tenant_proven"]]


def as_text(table: dict) -> str:
    """THREE NUMBERS, NEVER ONE.

    The states are reported apart and are never added together. `39 rules` is
    one claim, `16 have been run against a tenant` is another, and a catalogue
    that publishes the first while implying the second is the artefact this
    product exists to replace. The names are the delivery pipeline's -- see
    `docs/RULE-DELIVERY-PIPELINE.md` -- so that the gate, the contract and
    anybody reporting progress are using one vocabulary rather than three.
    """
    lines = [
        f"IMPLEMENTED       {table['rule_ready']} of {table['rules']} rules "
        f"(RULE-READY: sixteen conditions, code and deterministic tests)",
        f"TENANT-OBSERVED   {table['tenant_proven']} "
        f"(TENANT-PROVEN: a real directory produced the evidence)",
        f"PRODUCT-OBSERVED  {table['product_path']} "
        f"(PRODUCT-PATH: the command line, the bundle and a consumer)",
        "",
        f"  {table['collectable']} collectable · "
        f"{table['least_privilege_established']} with least privilege "
        f"established",
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
