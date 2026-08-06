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


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

#: Nothing external is fetched. A governance report is read by people who are
#: not allowed to load a font from somebody else's server while looking at
#: their own tenant's inventory.
_CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;padding:40px 20px;font:16px/1.6 ui-sans-serif,system-ui,sans-serif;
  background:#fff;color:#14151a}
main{max-width:820px;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 6px;font-weight:650}
h2{font-size:1.15rem;margin:38px 0 4px;font-weight:650}
h3{font-size:1rem;margin:0 0 8px;font-weight:650}
.meta{color:#5b5f68;font-size:.9rem;margin:0 0 4px}
.warn{border-left:4px solid #14151a;padding:10px 14px;margin:16px 0;
  background:#f5f5f7;font-size:.94rem}
table{border-collapse:collapse;margin:14px 0;font-size:.94rem}
th,td{text-align:left;padding:6px 16px 6px 0;border-bottom:1px solid #e6e7ea}
.card{border:1px solid #dcdde1;border-radius:8px;padding:18px 20px;margin:14px 0}
.card.fail,.card.invalid-evidence,.card.error{border-left:4px solid #14151a}
.card.unknown{border-left:4px dashed #14151a}
.tag{display:inline-block;font-size:.72rem;letter-spacing:.09em;
  text-transform:uppercase;font-weight:700;color:#5b5f68;margin-right:10px}
.msg{margin:10px 0}
dl{margin:12px 0 0;font-size:.92rem}
dt{color:#5b5f68;float:left;width:9em;clear:left}
dd{margin:0 0 4px 9em}
.limit{margin-top:14px;padding-top:12px;border-top:1px solid #e6e7ea;
  font-size:.92rem;color:#3d4048}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.88em}
a{color:inherit}
@media (prefers-color-scheme: dark){
  body{background:#101114;color:#e8e9ec}
  .meta,.tag,dt{color:#9aa0aa}
  .warn{background:#191a1e;border-color:#e8e9ec}
  th,td,.limit{border-color:#2a2c31}
  .card{border-color:#2a2c31}
  .card.fail,.card.invalid-evidence,.card.error,.card.unknown{border-left-color:#e8e9ec}
  .limit{color:#c3c6cc}
}
"""


def _esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def to_html(run: Run) -> str:
    """A self-contained page. No external requests, and no colour doing work.

    Colour is decoration here on purpose: the outcome is always spelled out in
    a word, so a printed page, a colour-blind reader and a screen reader all
    get the same report. An `unknown` that only differs from a `pass` by being
    a different shade is the green box under a new name.
    """
    resource = run.resource
    name = resource.get("display_name") or resource.get("id", "<unknown>")
    counts = run.counts()
    answered = counts[Outcome.PASS.value] + counts[Outcome.FAIL.value]
    total = len(run.results)

    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>Governance report: {_esc(name)}</title>",
        f"<style>{_CSS}</style></head><body><main>",
        f"<h1>Governance report: {_esc(name)}</h1>",
        f'<p class="meta">{_esc(resource.get("id", ""))} '
        f"({_esc(resource.get('type', '?'))})</p>",
    ]

    prov = run.provenance
    if prov:
        parts.append(
            f'<p class="meta">Collected {_esc(prov.get("collected_at", "?"))} '
            f"by {_esc(prov.get('collector', '?'))} "
            f"{_esc(prov.get('collector_version', ''))}, from "
            f"{_esc(prov.get('source_system', '?'))}.</p>"
        )
        if prov.get("identity_kind") == "delegated":
            parts.append(
                '<p class="warn"><strong>Identity: delegated.</strong> This run '
                "saw what one person sees. Nothing here may be read as a "
                "tenant-wide statement.</p>"
            )

    unavailable = (run.coverage or {}).get("unavailable") or {}
    if unavailable:
        rows = "".join(
            f"<tr><td><code>{_esc(b)}</code></td><td>{_esc(i.get('state', '?'))}"
            f"</td><td>{_esc(i.get('detail', ''))}</td></tr>"
            for b, i in sorted(unavailable.items())
        )
        parts.append("<h2>Not collected</h2>")
        parts.append(
            f"<table><tr><th>Block</th><th>State</th><th>Why</th></tr>{rows}</table>"
        )

    parts.append("<h2>Summary</h2>")
    parts.append(
        f"<p>{total} {'rule' if total == 1 else 'rules'} evaluated. "
        f"<strong>{answered} produced an answer.</strong></p>"
    )
    parts.append(
        "<table><tr><th>Outcome</th><th>Count</th></tr>"
        + "".join(
            f"<tr><td>{_LABEL[o]}</td><td>{counts[o.value]}</td></tr>" for o in _ORDER
        )
        + "</table>"
    )
    unresolved = counts[Outcome.UNKNOWN.value] + counts[Outcome.INVALID_EVIDENCE.value]
    if unresolved:
        parts.append(
            f'<p class="warn">{unresolved} '
            f"{'rule' if unresolved == 1 else 'rules'} could not be decided. "
            "That is not compliance: missing evidence is a fact about "
            "collection, not about the resource.</p>"
        )

    for outcome in _ORDER:
        results = [r for r in run.results if r.outcome is outcome]
        if not results:
            continue
        parts.append(f"<h2>{_LABEL[outcome]}</h2>")
        for result in results:
            parts.append(_html_card(result, outcome))

    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


def _html_card(result, outcome: Outcome) -> str:
    gloss = _BASIS_GLOSS.get(result.basis_type, "")
    rows = [
        f"<dt>Outcome</dt><dd><strong>{_LABEL[outcome]}</strong></dd>",
        f"<dt>Basis</dt><dd><strong>{_esc(result.basis_type)}</strong>"
        + (f" — {_esc(gloss)}" if gloss else "")
        + "</dd>",
        f"<dt>Severity</dt><dd>{_esc(result.severity)}</dd>",
    ]
    if result.evidence_used:
        rendered = ", ".join(
            f"<code>{_esc(e.path)}</code> = {_esc(e.describe())}"
            for e in result.evidence_used
        )
        rows.append(f"<dt>Evidence</dt><dd>{rendered}</dd>")
    for source in result.sources:
        rows.append(
            f'<dt>Source</dt><dd><a href="{_esc(source["url"])}">'
            f"{_esc(source['title'])}</a>, checked "
            f"{_esc(source['checked_at'])}</dd>"
        )

    extra = ""
    if outcome is Outcome.FAIL and result.remediation:
        extra += (
            f'<p class="limit"><strong>What to do:</strong> '
            f"{_esc(result.remediation)}</p>"
        )
    if outcome is Outcome.PASS and result.limitation:
        # On the pass, not behind a disclosure. A pass that hides what it does
        # not establish is the green box this project exists to remove.
        extra += (
            f'<p class="limit"><strong>This pass does not establish:'
            f"</strong> {_esc(result.limitation)}</p>"
        )
    if result.message_degraded:
        extra += (
            '<p class="limit">A value in this message was not collected. '
            "The outcome did not depend on it; the sentence does.</p>"
        )
    if outcome is Outcome.ERROR and result.engine_detail:
        extra += (
            f'<p class="limit">Engine: <code>{_esc(result.engine_detail)}</code></p>'
        )

    return (
        f'<div class="card {outcome.value}">'
        f'<h3><span class="tag">{_LABEL[outcome]}</span>'
        f"{_esc(result.rule_id)} v{_esc(result.rule_version)}</h3>"
        f'<p class="msg">{_esc(result.message)}</p>'
        f"<dl>{''.join(rows)}</dl>{extra}</div>"
    )
