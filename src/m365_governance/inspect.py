"""Reading the repository and the evidence, without evaluating anything.

`list-rules`, `show-rule` and `stats` all answer questions somebody has before
they trust a result: what is in here, what does this rule actually claim, and
what did the collector manage to see.
"""

from __future__ import annotations

from pathlib import Path

from .loader import load_evidence, load_rules
from .results import Outcome

#: Ordered so that the strongest claim reads first. This is presentation only;
#: nothing in the engine depends on an ordering of `basis`.
BASIS_ORDER = [
    "requirement",
    "documented-limit",
    "documented-guidance",
    "convention",
    "opinion",
]

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]
    head = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()
    body = [
        "  ".join(c.ljust(widths[i]) for i, c in enumerate(row)).rstrip()
        for row in rows
    ]
    return "\n".join([head, "-" * len(head), *body])


def list_rules(directory: Path) -> str:
    rules = [loaded.data for loaded in load_rules(directory)]
    if not rules:
        return f"No rules under {directory}."

    def key(rule: dict) -> tuple:
        basis = rule["basis"]["type"]
        severity = rule["severity"]["default"]
        return (
            BASIS_ORDER.index(basis) if basis in BASIS_ORDER else len(BASIS_ORDER),
            SEVERITY_ORDER.index(severity)
            if severity in SEVERITY_ORDER
            else len(SEVERITY_ORDER),
            rule["id"],
        )

    rows = [
        [
            rule["id"],
            f"v{rule['version']}",
            rule["basis"]["type"],
            rule["severity"]["default"],
            rule["resource_type"],
            rule["title"],
        ]
        for rule in sorted(rules, key=key)
    ]
    table = _table(["ID", "VERSION", "BASIS", "SEVERITY", "APPLIES TO", "TITLE"], rows)

    counts: dict[str, int] = {}
    for rule in rules:
        counts[rule["basis"]["type"]] = counts.get(rule["basis"]["type"], 0) + 1
    summary = ", ".join(f"{counts[b]} {b}" for b in BASIS_ORDER if b in counts)
    return f"{table}\n\n{len(rules)} rules: {summary}."


def _value(raw) -> str:
    """A rule is YAML, so its booleans read as `false`, never as Python's."""
    if isinstance(raw, bool):
        return "true" if raw else "false"
    return str(raw)


def _wrap(text: str, width: int = 76, indent: str = "  ") -> str:
    import textwrap

    return "\n".join(
        textwrap.fill(
            " ".join(paragraph.split()),
            width=width,
            initial_indent=indent,
            subsequent_indent=indent,
        )
        for paragraph in text.strip().split("\n\n")
        if paragraph.strip()
    )


def show_rule(directory: Path, rule_id: str) -> str:
    rules = {loaded.data["id"]: loaded for loaded in load_rules(directory)}
    if rule_id not in rules:
        known = ", ".join(sorted(rules)) or "none"
        raise KeyError(f"no rule with id {rule_id!r}. Known ids: {known}")

    loaded = rules[rule_id]
    rule = loaded.data
    basis = rule["basis"]
    out: list[str] = []

    out.append(f"{rule['id']}  v{rule['version']}")
    out.append(rule["title"])
    out.append("")
    out.append(_wrap(rule["description"]))
    out.append("")

    out.append(f"BASIS       {basis['type']}")
    out.append(
        _wrap(basis.get("rationale", ""), indent="            ")
        if basis.get("rationale")
        else ""
    )
    if "limit" in basis:
        limit = basis["limit"]
        out.append(f"            limit: {limit['value']:,} {limit['unit']}")
    out.append("")

    severity = rule["severity"]
    out.append(
        f"SEVERITY    {severity['default']}"
        + ("  (configurable)" if severity.get("configurable") else "")
    )
    out.append(_wrap(severity["rationale"], indent="            "))
    out.append("")

    out.append("EVIDENCE    what the rule needs, and cannot decide without")
    for req in rule["evidence_requirements"]:
        out.append(f"            {req['path']}  ({req['type']})")
    out.append("")

    if "applicability" in rule:
        app = rule["applicability"]
        out.append(
            f"APPLIES     when {app['evidence']} {app['operator']} "
            f"{_value(app.get('value'))}"
        )
        out.append(
            "            otherwise the outcome is not-applicable, which is not a pass"
        )
        out.append("")

    cond = rule["condition"]
    out.append(
        f"CONDITION   {cond['evidence']} {cond['operator']} {_value(cond.get('value'))}"
    )
    out.append("            true means fail: a condition names the case being reported")
    out.append("")

    out.append("OUTCOMES")
    for state in ("pass", "fail", "unknown", "not_applicable", "invalid_evidence"):
        label = state.replace("_", "-")
        out.append(f"  {label}")
        out.append(_wrap(rule["outcomes"][state]["message"], indent="      "))
    out.append("")

    out.append("THIS RULE CAN PASS WHILE THE PROBLEM SURVIVES")
    out.append(_wrap(rule["limitations"]["passes_without_resolving"]))
    other = rule["limitations"].get("other") or []
    if other:
        out.append("")
        out.append("IT ALSO DOES NOT ESTABLISH")
        for item in other:
            out.append(_wrap(item))
            out.append("")

    if rule.get("remediation"):
        out.append("REMEDIATION")
        out.append(_wrap(rule["remediation"]))
        out.append("")

    sources = basis.get("sources") or []
    if sources:
        out.append("SOURCES")
        for source in sources:
            out.append(f"  {source['title']}")
            out.append(f"    {source['url']}")
            out.append(f"    checked {source['checked_at']}")
    else:
        out.append("SOURCES     none, and none is required for this basis")

    out.append("")
    out.append(f"FILE        {loaded.path}")
    return "\n".join(line for line in out).replace("\n\n\n", "\n\n").rstrip() + "\n"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def _walk_facts(node, prefix: str = "") -> list[tuple[str, dict]]:
    """Every fact node in the tree, with its path."""
    found: list[tuple[str, dict]] = []
    if not isinstance(node, dict):
        return found
    if "state" in node:
        found.append((prefix, node))
        return found
    for key, value in node.items():
        found.extend(_walk_facts(value, f"{prefix}.{key}" if prefix else key))
    return found


def stats(path: Path) -> str:
    evidence = load_evidence(path).data
    resource = evidence.get("resource", {})
    provenance = evidence.get("provenance", {})
    coverage = evidence.get("coverage", {})
    facts = evidence.get("facts", {})

    out: list[str] = []
    out.append("EVIDENCE")
    out.append(f"  resource          {resource.get('id', '<unknown>')}")
    out.append(f"  type              {resource.get('type', '?')}")
    out.append(f"  collected         {provenance.get('collected_at', '?')}")
    out.append(
        f"  collector         {provenance.get('collector', '?')} "
        f"{provenance.get('collector_version', '')}".rstrip()
    )

    identity = provenance.get("identity_kind", "?")
    out.append(f"  identity          {identity}")
    if identity == "delegated":
        out.append("                    this run saw what one person sees")
    out.append(f"  acquisition       {provenance.get('acquisition', '?')}")
    if provenance.get("acquisition") == "imported":
        source = provenance.get("import_source", {})
        out.append(
            f"  export tool       {source.get('tool', '?')} "
            f"{source.get('version', '')}".rstrip()
        )
        out.append(f"  exported at       {source.get('exported_at', '?')}")
        if source.get("exported_by"):
            out.append(f"  exported by       {source['exported_by']}")
        out.append("                    completeness cannot be verified by this engine")
    out.append("")

    requested = coverage.get("requested", [])
    completed = coverage.get("completed", [])
    unavailable = coverage.get("unavailable", {}) or {}
    out.append("COVERAGE")
    out.append(f"  requested         {len(requested)}  {', '.join(requested) or '-'}")
    out.append(f"  completed         {len(completed)}  {', '.join(completed) or '-'}")
    if unavailable:
        out.append(f"  not collected     {len(unavailable)}")
        for block, info in sorted(unavailable.items()):
            # A NULL ENTRY IS A DEFECT IN THE PRODUCER AND MUST NOT BE A CRASH
            # HERE. The first live licensing run wrote `"usage": null` for an
            # area that had completed, and this line raised on a member of
            # `None`: the collection had succeeded, the tenant had been read,
            # and the tool could not open its own document. The writer no
            # longer emits one; a reader still meets documents it did not
            # write, and "a refusal is a state, not a crash" applies to
            # malformed input too.
            if not isinstance(info, dict):
                out.append(f"    {block}: ? — no reason recorded")
                continue
            out.append(
                f"    {block}: {info.get('state', '?')} — {info.get('detail', '')}"
            )
    out.append("")

    nodes = _walk_facts(facts)
    by_state: dict[str, int] = {}
    for _path, node in nodes:
        by_state[node["state"]] = by_state.get(node["state"], 0) + 1

    out.append("FACTS")
    out.append(f"  fact nodes        {len(nodes)}")
    for state in sorted(by_state):
        out.append(f"    {state:<16}{by_state[state]}")
    out.append("")

    aggregates = [(p, n) for p, n in nodes if "expansion_complete" in n]
    if aggregates:
        out.append("EXPANSION")
        for path, node in aggregates:
            complete = node.get("expansion_complete")
            groups = node.get("groups") or []
            direct = node.get("direct") or []
            out.append(f"  {path}")
            out.append(f"    direct          {len(direct)}")
            out.append(f"    groups          {len(groups)}")
            out.append(f"    complete        {'yes' if complete else 'no'}")
            if complete:
                out.append(f"    count           {node.get('effective_count')}")
            else:
                out.append(f"    at least        {node.get('minimum_count')}")
                out.append(
                    "                    a lower bound. The engine can "
                    "prove a pass from it,"
                )
                out.append("                    and can never prove a fail.")
        out.append("")

    decidable = [p for p, n in nodes if n["state"] in ("observed", "partial")]
    out.append(
        f"{len(decidable)} of {len(nodes)} facts are readable. "
        f"The rest produce {Outcome.UNKNOWN.value} or "
        f"{Outcome.INVALID_EVIDENCE.value}, never a pass."
    )
    return "\n".join(out) + "\n"
