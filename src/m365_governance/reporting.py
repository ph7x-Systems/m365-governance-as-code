"""Reports.

A report shows its work. Every finding carries what kind of claim it is, the
evidence it was derived from, and what it does not establish.

`unknown` and `not-applicable` are never aggregated as passes. A rule that
never applied established nothing, and a rule that could not decide is the
absence of an answer.
"""

from __future__ import annotations

import json

from . import attention
from .results import Outcome, Run, RunSet

#: The order a report groups its findings in — DERIVED, never written here.
#:
#: This was a hand-written list, and the Workbench held a different one:
#: `pass` came before `not-applicable` there, and an engine error was nowhere
#: in it at all. Two surfaces of one product, each internally consistent,
#: disagreeing about what a reader should see first. Neither was wrong on its
#: own terms, which is what made it invisible.
#:
#: Ties keep the enumeration's own order, so the sequence is stable across runs
#: rather than depending on how a dictionary happened to iterate.
_OUTCOMES = list(Outcome)
_ORDER = sorted(
    Outcome,
    key=lambda o: (attention.rank_of_outcome(o.value), _OUTCOMES.index(o)),
)

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
    # Before the counts, because what needs a person is the question somebody
    # opens a governance report with, and a table of six numbers does not
    # answer it.
    lines.extend(_attention_lines(run))
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
        f"- Source: {prov.get('source_system', '?')}"
        + (f" via {prov['source_api']}" if prov.get("source_api") else ""),
    ]
    if run.rule_source:
        lines.append(f"- Rules: {run.rule_source}")
    identity = prov.get("identity_kind")
    # Keyed on acquisition, not on identity. They were one field, so this
    # warning was asking who observed the evidence in order to answer how it
    # got here — and an import that named its collecting identity lost the
    # warning entirely, which is the one case where it matters most.
    if prov.get("acquisition") == "imported":
        source = prov.get("import_source", {})
        lines.append(
            f"- **Evidence imported from {source.get('tool', 'another tool')}"
            + (f" {source['version']}" if source.get("version") else "")
            + ".** This assessment is based on imported evidence. Collection "
            "completeness cannot be verified by this engine."
        )
        detail = [
            f"exported {source['exported_at']}" if source.get("exported_at") else "",
            f"by {source['exported_by']}" if source.get("exported_by") else "",
        ]
        detail = ", ".join(part for part in detail if part)
        if detail:
            lines.append(f"- Export: {detail}")
        if source.get("detail"):
            lines.append(f"- {source['detail']}")
        stale = _export_gap(prov)
        if stale:
            lines.append(f"- **{stale}**")
    elif identity == "delegated":
        lines.append(
            "- **Identity: delegated.** This run saw what one person sees. "
            "Nothing here may be read as a tenant-wide statement."
        )
    else:
        scopes = ", ".join(prov.get("scopes", [])) or "none recorded"
        lines.append(f"- Identity: {identity or '?'}, scopes: {scopes}")
    return lines


def _export_gap(prov: dict) -> str:
    """An export produced long after the scan that fed it.

    `collected_at` is when the facts were observed; `import_source.exported_at`
    is when the file was written. They are usually the same moment. When they
    are not, the report is older than it looks, and the person reading it is
    the last one able to notice.
    """
    from datetime import datetime

    source = prov.get("import_source", {})
    observed, exported = prov.get("collected_at"), source.get("exported_at")
    if not observed or not exported:
        return ""
    try:
        a = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        b = datetime.fromisoformat(exported.replace("Z", "+00:00"))
    except ValueError:
        return ""
    days = (b - a).days
    if days < 1:
        return ""
    return (
        f"The facts are {days} days older than the export that carries them. "
        f"They were observed on {a.date()} and written out on {b.date()}."
    )


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


#: How each state reads at the top of a report. Wording only — WHICH state a
#: run is in is the engine's judgement, arriving on the document, and this maps
#: it to a sentence rather than working it out again.
_ATTENTION_LABEL = {
    "act": "Something here is outside what the vendor documents.",
    "review": "Nothing is outside a documented requirement. Some findings are "
    "worth weighing.",
    "observe": "Part of this could not be answered, so the report describes "
    "less than the resource.",
    "none": "Everything asked was read, and nothing failed.",
    "not-evaluated": "No judgement was formed here.",
}


def _attention_lines(run: Run) -> list[str]:
    """What the engine says needs a person, and why.

    THE SAME SENTENCE THE WORKBENCH SHOWS, from the same field. The two
    surfaces used to answer this separately — the Workbench decided from counts
    that `fail > 0` meant act, and the command line never asked the question at
    all — so a report and a window over one run could lead with different
    things and neither was wrong on its own terms.
    """
    judged = run.to_dict()["attention"]
    lines = [
        "## Attention",
        "",
        f"**{_ATTENTION_LABEL.get(judged['state'], judged['state'])}**",
        "",
    ]
    # The reasons, never a bare verdict.
    lines.extend(f"- {because}" for because in judged["because"])
    lines.append("")
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
        identity = prov.get("identity_kind")
        if prov.get("acquisition") == "imported":
            source = prov.get("import_source", {})
            exported = ", ".join(
                part
                for part in (
                    f"exported {source['exported_at']}"
                    if source.get("exported_at")
                    else "",
                    f"by {source['exported_by']}" if source.get("exported_by") else "",
                )
                if part
            )
            parts.append(
                '<p class="warn"><strong>Evidence imported from '
                f"{_esc(source.get('tool', 'another tool'))}.</strong> This "
                "assessment is based on imported evidence. Collection "
                "completeness cannot be verified by this engine."
                + (f" ({_esc(exported)})" if exported else "")
                + "</p>"
            )
            gap = _export_gap(prov)
            if gap:
                parts.append(f'<p class="warn"><strong>{_esc(gap)}</strong></p>')
        elif identity == "delegated":
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


# ---------------------------------------------------------------------------
# Many documents at once
# ---------------------------------------------------------------------------


def _class_lines(runs: list[Run]) -> list[str]:
    """What was observed, by kind, and what a profile moved down the page.

    Set aside is not excluded. Every finding on a set-aside resource is still
    evaluated, still counted here, and still printed below. A profile that
    could drop a resource could hide a library holding 60,000 unique scopes
    because SharePoint happens to call it plumbing.
    """
    by_class: dict[str, int] = {}
    for run in runs:
        by_class[run.resource_class or "unclassified"] = (
            by_class.get(run.resource_class or "unclassified", 0) + 1
        )
    aside = [r for r in runs if r.set_aside]

    lines = [f"{len(runs)} resources observed"]
    for name in sorted(by_class):
        lines.append(f"  {name:<16}{by_class[name]}")
    if aside:
        answered = sum(
            1 for r in aside for result in r.results if result.outcome.is_answer
        )
        lines.append(
            f"  set aside by profile: {len(aside)}, carrying {answered} answers. "
            f"Reported below, not removed."
        )
    return lines


def many_to_markdown(value: list[Run] | RunSet) -> str:
    """One report over many documents, with the set-aside ones at the end."""
    run_set = value if isinstance(value, RunSet) else RunSet(value)
    runs = run_set.runs
    if not runs:
        return "No evidence documents.\n"

    total = {o.value: 0 for o in Outcome}
    for run in runs:
        for key, value in run.counts().items():
            total[key] += value
    answered = total[Outcome.PASS.value] + total[Outcome.FAIL.value]
    evaluated = sum(len(run.results) for run in runs)

    lines = ["# Governance report", ""]
    lines.extend(
        f"- {line}" if i == 0 else f"  {line.strip()}"
        for i, line in enumerate(_class_lines(runs))
    )
    lines.append("")

    coverage = run_set.run_coverage()
    expected = coverage.get("expected")
    if expected is None:
        lines.append(
            f"> **Run coverage: not established.** {coverage.get('detail', '')}"
        )
    else:
        lines.append(
            f"> **Run coverage:** {coverage.get('observed', len(runs))} of "
            f"{expected} expected resources are stored."
        )
    lines.append("")

    delegated = any(
        (run.provenance or {}).get("identity_kind") == "delegated" for run in runs
    )
    if delegated:
        lines.append(
            "> **Identity: delegated.** These runs saw what one person sees. "
            "Nothing here may be read as a tenant-wide statement."
        )
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"{evaluated} rule evaluations across {len(runs)} resources. "
        f"**{answered} produced an answer.**"
    )
    lines.append("")
    lines.append("| Outcome | Count |")
    lines.append("|---|---|")
    for outcome in _ORDER:
        lines.append(f"| {_LABEL[outcome]} | {total[outcome.value]} |")
    lines.append("")

    unresolved = total[Outcome.UNKNOWN.value] + total[Outcome.INVALID_EVIDENCE.value]
    if unresolved:
        lines.append(
            f"{unresolved} could not be decided. That is not compliance: missing "
            f"evidence is a fact about collection, not about the resource."
        )
        lines.append("")

    for heading, selected in (
        ("Findings", [r for r in runs if not r.set_aside]),
        ("Set aside by profile", [r for r in runs if r.set_aside]),
    ):
        interesting = [
            run
            for run in selected
            if any(r.outcome is not Outcome.PASS for r in run.results)
        ]
        if not selected:
            continue
        lines.append(f"## {heading}")
        lines.append("")
        if heading.startswith("Set aside"):
            lines.append(
                "The profile moved these down the page. Nothing was removed, "
                "and a finding here counts the same as one above it."
            )
            lines.append("")
        if not interesting:
            lines.append(f"{len(selected)} resources, nothing but passes.")
            lines.append("")
            continue
        for run in interesting:
            name = run.resource.get("display_name") or run.resource.get("id", "?")
            klass = f" · {run.resource_class}" if run.resource_class else ""
            lines.append(f"### {_esc_md(name)}{klass}")
            lines.append("")
            for result in run.results:
                if result.outcome is Outcome.PASS:
                    continue
                lines.append(
                    f"- **{_LABEL[result.outcome]}** · {result.rule_id} "
                    f"v{result.rule_version} · {result.basis_type}"
                )
                lines.append(f"  {result.message}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _esc_md(text: str) -> str:
    return str(text).replace("|", "\\|")


def many_to_json(value: list[Run] | RunSet) -> str:
    run_set = value if isinstance(value, RunSet) else RunSet(value)
    return json.dumps(run_set.to_dict(), indent=2, ensure_ascii=False) + "\n"


def many_to_html(value: list[Run] | RunSet) -> str:
    """The many-resource report as one self-contained page.

    It carries the same facts as the Markdown and JSON forms, because a report
    that said one thing on paper and another in the browser would be two
    reports. The run coverage line, the delegated warning, the counts and the
    per-resource findings are all here; colour still does no work, so a printed
    copy reads the same.
    """
    run_set = value if isinstance(value, RunSet) else RunSet(value)
    runs = run_set.runs

    total = run_set.counts()
    answered = total[Outcome.PASS.value] + total[Outcome.FAIL.value]
    evaluated = sum(len(run.results) for run in runs)

    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>Governance report</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<h1>Governance report</h1>",
    ]

    if not runs:
        parts.append("<p>No evidence documents.</p>")
        parts.append("</main></body></html>")
        return "\n".join(parts) + "\n"

    by_class = run_set.by_class()
    observed = ", ".join(f"{by_class[name]} {name}" for name in sorted(by_class))
    parts.append(
        f'<p class="meta">{len(runs)} resources observed: {_esc(observed)}.</p>'
    )

    coverage = run_set.run_coverage()
    expected = coverage.get("expected")
    if expected is None:
        parts.append(
            '<p class="warn"><strong>Run coverage: not established.</strong> '
            f"{_esc(coverage.get('detail', ''))}</p>"
        )
    else:
        parts.append(
            f'<p class="warn"><strong>Run coverage:</strong> '
            f"{_esc(coverage.get('observed', len(runs)))} of {_esc(expected)} "
            "expected resources are stored.</p>"
        )

    if any((run.provenance or {}).get("identity_kind") == "delegated" for run in runs):
        parts.append(
            '<p class="warn"><strong>Identity: delegated.</strong> These runs '
            "saw what one person sees. Nothing here may be read as a tenant-wide "
            "statement.</p>"
        )

    parts.append("<h2>Summary</h2>")
    parts.append(
        f"<p>{evaluated} rule evaluations across {len(runs)} resources. "
        f"<strong>{answered} produced an answer.</strong></p>"
    )
    parts.append(
        "<table><tr><th>Outcome</th><th>Count</th></tr>"
        + "".join(
            f"<tr><td>{_LABEL[o]}</td><td>{total[o.value]}</td></tr>" for o in _ORDER
        )
        + "</table>"
    )
    unresolved = total[Outcome.UNKNOWN.value] + total[Outcome.INVALID_EVIDENCE.value]
    if unresolved:
        parts.append(
            f'<p class="warn">{unresolved} could not be decided. That is not '
            "compliance: missing evidence is a fact about collection, not about "
            "the resource.</p>"
        )

    for heading, selected in (
        ("Findings", [r for r in runs if not r.set_aside]),
        ("Set aside by profile", [r for r in runs if r.set_aside]),
    ):
        if not selected:
            continue
        parts.append(f"<h2>{heading}</h2>")
        if heading.startswith("Set aside"):
            parts.append(
                '<p class="warn">The profile moved these down the page. Nothing '
                "was removed, and a finding here counts the same as one above "
                "it.</p>"
            )
        interesting = [
            run
            for run in selected
            if any(r.outcome is not Outcome.PASS for r in run.results)
        ]
        if not interesting:
            parts.append(f"<p>{len(selected)} resources, nothing but passes.</p>")
            continue
        for run in interesting:
            name = run.resource.get("display_name") or run.resource.get("id", "?")
            klass = f" · {run.resource_class}" if run.resource_class else ""
            parts.append(f"<h3>{_esc(name)}{_esc(klass)}</h3>")
            for result in run.results:
                if result.outcome is Outcome.PASS:
                    continue
                parts.append(_html_card(result, result.outcome))

    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# a comparison, for a person
# ---------------------------------------------------------------------------


def comparison_to_markdown(document: dict) -> str:
    """One comparison, rendered.

    A projection and never a second opinion: every line here is read out of the
    document, including which changes there are and what each one means. If
    this rendering and the JSON ever disagreed, one of them would be computing
    something, and a reader would have no way to tell which.
    """
    before, after = document["before"], document["after"]
    diff = document["diff"]
    changes = diff["changes"]

    lines = [
        "# What changed",
        "",
        f"- Tenant: {before['tenant']['host']}",
        f"- Before: {before['created_at']}  `{before['assessment_id'][:12]}`",
        f"- After:  {after['created_at']}  `{after['assessment_id'][:12]}`",
        f"- Produced by: {diff['produced_by']}",
        "",
    ]

    if not changes:
        lines += [
            "Nothing changed. Every resource and rule that appears in one "
            "assessment appears in the other with the same outcome, the same "
            "rule version and the same evidence.",
            "",
        ]
        return "\n".join(lines)

    kinds = {"changed": [], "added": [], "removed": []}
    for change in changes:
        kinds[change["kind"]].append(change)

    lines += [f"{len(changes)} changes.", ""]

    for kind, heading in (
        ("changed", "Changed"),
        ("added", "Newly evaluated"),
        ("removed", "No longer evaluated"),
    ):
        if not kinds[kind]:
            continue
        lines += [f"## {heading}", ""]
        for change in kinds[kind]:
            movement = (
                f"{change['before']} → {change['after']}"
                if kind == "changed"
                else (change["after"] or change["before"])
            )
            lines.append(
                f"- **{change['rule']}** on `{change['resource']}`: {movement}"
            )
            if change.get("changes"):
                lines.append(f"  - observed to differ: {', '.join(change['changes'])}")
            state = change.get("attribution", {}).get("state")
            if state == "ambiguous":
                factors = ", ".join(change["attribution"]["factors"])
                lines.append(
                    f"  - **why is not established**: {factors} both moved, and "
                    "nothing here evaluated which one produced the outcome"
                )
            elif state == "not-evaluated":
                lines.append(
                    "  - **why is not established**: nobody evaluated causality"
                )
        lines.append("")

    lines += [
        "> **What this does not say.** These are observations about two "
        "recorded states. Which change produced which outcome is a separate "
        "question, and answering it needs the older evidence re-evaluated "
        "against the newer rule — which nothing here did.",
        "",
    ]
    return "\n".join(lines)
