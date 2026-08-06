"""Reports.

A report shows its work. Every finding carries what kind of claim it is, the
evidence it was derived from, and what it does not establish.

`unknown` and `not-applicable` are never aggregated as passes. A rule that
never applied established nothing, and a rule that could not decide is the
absence of an answer.
"""

from __future__ import annotations

import json

from .results import Outcome, Run

_ORDER = [
    Outcome.FAIL,
    Outcome.INVALID_EVIDENCE,
    Outcome.UNKNOWN,
    Outcome.ERROR,
    Outcome.NOT_APPLICABLE,
    Outcome.PASS,
]

_LABEL = {
    Outcome.PASS: "Pass",
    Outcome.FAIL: "Fail",
    Outcome.UNKNOWN: "Unknown",
    Outcome.NOT_APPLICABLE: "Not applicable",
    Outcome.INVALID_EVIDENCE: "Invalid evidence",
    Outcome.ERROR: "Error",
}

_BASIS_GLOSS = {
    "requirement": "the product enforces this",
    "documented-limit": "a boundary the product imposes",
    "documented-guidance": (
        "Microsoft recommends this; the product permits the alternative"
    ),
    "convention": "widely held practice, not documented as a rule",
    "opinion": "our position, stated as ours",
}


def to_json(run: Run) -> str:
    return json.dumps(run.to_dict(), indent=2, ensure_ascii=False) + "\n"


def to_markdown(run: Run) -> str:
    lines: list[str] = []
    resource = run.resource
    name = resource.get("display_name") or resource.get("id", "<unknown>")

    lines.append(f"# Governance report: {name}")
    lines.append("")
    lines.append(
        f"- Resource: `{resource.get('id', '<unknown>')}` ({resource.get('type', '?')})"
    )
    lines.extend(_provenance_lines(run))
    lines.extend(_coverage_lines(run))
    lines.append("")
    lines.extend(_summary_lines(run))
    lines.append("")

    for outcome in _ORDER:
        results = [r for r in run.results if r.outcome is outcome]
        if not results:
            continue
        lines.append(f"## {_LABEL[outcome]}")
        lines.append("")
        for result in results:
            lines.extend(_result_lines(result))
    return "\n".join(lines).rstrip() + "\n"


def _provenance_lines(run: Run) -> list[str]:
    prov = run.provenance
    if not prov:
        return []
    lines = [
        f"- Collected: {prov.get('collected_at', '?')} "
        f"by `{prov.get('collector', '?')}` "
        f"{prov.get('collector_version', '')}".rstrip(),
        f"- Source: {prov.get('source_system', '?')} via {prov.get('source_api', '?')}",
    ]
    identity = prov.get("identity_kind")
    if identity == "delegated":
        lines.append(
            "- **Identity: delegated.** This run saw what one person sees. "
            "Nothing here may be read as a tenant-wide statement."
        )
    else:
        scopes = ", ".join(prov.get("scopes", [])) or "none recorded"
        lines.append(f"- Identity: {identity or '?'}, scopes: {scopes}")
    return lines


def _coverage_lines(run: Run) -> list[str]:
    unavailable = (run.coverage or {}).get("unavailable") or {}
    if not unavailable:
        return []
    lines = ["- **Not collected:**"]
    for block, info in sorted(unavailable.items()):
        lines.append(
            f"  - `{block}` — {info.get('state', '?')}: {info.get('detail', '')}"
        )
    return lines


def _summary_lines(run: Run) -> list[str]:
    counts = run.counts()
    answered = counts[Outcome.PASS.value] + counts[Outcome.FAIL.value]
    total = len(run.results)
    lines = [
        "## Summary",
        "",
        f"{total} {'rule' if total == 1 else 'rules'} evaluated. "
        f"**{answered} produced an answer.**",
        "",
        "| Outcome | Count |",
        "|---|---|",
    ]
    for outcome in _ORDER:
        lines.append(f"| {_LABEL[outcome]} | {counts[outcome.value]} |")
    lines.append("")
    unresolved = counts[Outcome.UNKNOWN.value] + counts[Outcome.INVALID_EVIDENCE.value]
    if unresolved:
        lines.append(
            f"{unresolved} {'rule' if unresolved == 1 else 'rules'} could not be "
            f"decided. That is not compliance: "
            f"missing evidence is a fact about collection, not about the resource."
        )
    return lines


def _result_lines(result) -> list[str]:
    gloss = _BASIS_GLOSS.get(result.basis_type, "")
    lines = [
        f"### {result.rule_id} v{result.rule_version}",
        "",
        result.message,
        "",
        f"- Basis: **{result.basis_type}** — {gloss}"
        if gloss
        else f"- Basis: **{result.basis_type}**",
        f"- Severity: {result.severity}",
    ]
    if result.evidence_used:
        rendered = ", ".join(
            f"`{e.path}` = {e.describe()}" for e in result.evidence_used
        )
        lines.append(f"- Evidence: {rendered}")
    if result.message_degraded:
        lines.append(
            "- A value in this message was not collected. The outcome did not "
            "depend on it, the sentence does."
        )
    if result.outcome is Outcome.ERROR and result.engine_detail:
        lines.append(f"- Engine: {result.engine_detail}")
    for source in result.sources:
        lines.append(
            f"- Source: [{source['title']}]({source['url']}) "
            f"— checked {source['checked_at']}"
        )
    if result.outcome is Outcome.FAIL and result.remediation:
        lines.append("")
        lines.append(f"**What to do:** {result.remediation}")
    if result.outcome is Outcome.PASS and result.limitation:
        lines.append("")
        lines.append(f"**This pass does not establish:** {result.limitation}")
    lines.append("")
    return lines
