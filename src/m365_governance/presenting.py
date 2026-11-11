"""Evidence, laid out for a terminal. A view, and never the evidence.

`m365g spo site list` answers in the terminal, and what it prints is this
module's rendering of the evidence documents the collection wrote. The
documents are the product: they carry provenance, coverage and the schema. A
view carries none of that and replaces none of it, which is why the JSON view
is the documents themselves and every other view is derived from them without
adding a word of its own.

NOTHING IS CONCLUDED HERE. An observed fact is shown as what was observed, any
other state is shown as that state and never as a value, an unavailable area
is shown as unavailable, and nothing is counted as good or bad: that is what
rules are for. A count that does appear is the length of a list the document
holds, named for the list it counts.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

FORMATS = ("text", "json", "csv", "md")

#: The columns every view starts with, in this order. Stable: a consumer of the
#: CSV may rely on them. Fact columns follow, sorted by name.
LEADING = (
    "resource_type",
    "name",
    "url",
    "native_id",
    "tenant",
    "collected_at",
    "completed",
    "unavailable",
)


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


#: A short list of plain values is shown; a longer one, or a list of objects,
#: is shown as how many entries it holds. The JSON view carries all of it.
SHOWN = 6

#: What a fact carries besides what it found. `raw` repeats the value beside
#: the field it came from and `detail` is prose; both are in the JSON view.
_BESIDE = ("state", "value", "raw", "detail")


def _value(value: Any) -> str:
    if isinstance(value, list):
        plain = all(not isinstance(item, (dict, list)) for item in value)
        if plain and 0 < len(value) <= SHOWN:
            return ", ".join(_scalar(item) for item in value)
        return f"{len(value)} entries"
    if isinstance(value, dict):
        return "{" + ", ".join(sorted(value)) + "}"
    return _scalar(value)


def _is_fact(value: Any) -> bool:
    return isinstance(value, dict) and "state" in value


def fact(value: Any) -> str:
    """One fact in one cell.

    DECLARED TRANSLATION, and the only one this module makes. An `observed`
    fact is shown as what was observed. Any other state is shown as the state
    itself in square brackets and no value beside it, so a cell can never be
    read as an observation that was not made: `[permission-denied]` is the
    collector's word, unchanged. The contract value behind every cell is in
    the JSON view.
    """
    if not isinstance(value, dict):
        return _value(value)
    parts = []
    state = value.get("state")
    if state is not None and state != "observed":
        parts.append(f"[{_scalar(state)}]")
    elif "value" in value:
        parts.append(_value(value["value"]))
    for key in sorted(k for k in value if k not in _BESIDE):
        inner = value[key]
        if inner is None:
            continue
        if isinstance(inner, list):
            parts.append(f"{key}: {len(inner)} entries")
        elif _is_fact(inner):
            # A fact that holds facts of its own: `owners` carries its two
            # counts this way. Each is shown by the same rule as any fact,
            # never as the names of its keys.
            parts.append(f"{key}={fact(inner)}")
        elif isinstance(inner, dict):
            parts.append(f"{key}: {_value(inner)}")
        else:
            parts.append(f"{key}={_scalar(inner)}")
    return "; ".join(parts)


def cells(facts: dict) -> dict[str, Any]:
    """Every fact a document holds, by the name a person would look for.

    Collectors group facts in families -- `site.storage_used_mb`,
    `hub.requires_join_approval` -- and a family shown as one cell is a cell
    listing the names of its own keys, which is what this printed until a
    real tenant was read with it. A family becomes one column per fact,
    named `family.fact`, the path a rule uses for the same fact.
    """
    out: dict[str, Any] = {}
    for name, value in facts.items():
        family = (
            isinstance(value, dict)
            and not _is_fact(value)
            and any(isinstance(inner, dict) for inner in value.values())
        )
        if family:
            for key, inner in value.items():
                out[f"{name}.{key}"] = inner
        else:
            out[name] = value
    return out


def table(documents: list[dict]) -> tuple[list[str], list[list[str]]]:
    """Headers and rows for the documents: one row per resource."""
    flat = [cells(doc.get("facts", {})) for doc in documents]
    names = sorted({name for facts in flat for name in facts})
    rows = []
    for doc, facts in zip(documents, flat, strict=True):
        resource = doc.get("resource", {})
        provenance = doc.get("provenance", {})
        coverage = doc.get("coverage", {})
        unavailable = coverage.get("unavailable") or {}
        rows.append(
            [
                _scalar(resource.get("type", "")),
                _scalar(resource.get("display_name") or ""),
                _scalar(resource.get("url") or ""),
                _scalar(resource.get("native_id", "")),
                _scalar((resource.get("tenant") or {}).get("host") or ""),
                _scalar(provenance.get("collected_at", "")),
                ", ".join(coverage.get("completed") or []),
                ", ".join(sorted(unavailable)),
                *[fact(facts[name]) if name in facts else "" for name in names],
            ]
        )
    return [*LEADING, *names], rows


def _text(documents: list[dict]) -> str:
    if not documents:
        return "Nothing was read.\n"
    lines = []
    for doc in documents:
        resource = doc.get("resource", {})
        coverage = doc.get("coverage", {})
        title = resource.get("display_name") or resource.get("native_id", "")
        where = resource.get("url") or ""
        lines.append(title if title == where else f"{title}  {where}".rstrip())
        lines.append(f"  {resource.get('type', '')} · {resource.get('native_id', '')}")
        facts = cells(doc.get("facts", {}))
        unavailable = coverage.get("unavailable") or {}
        width = max((len(name) for name in [*facts, *unavailable]), default=0)
        for name in sorted(facts):
            shown = fact(facts[name])
            detail = facts[name].get("detail") if _is_fact(facts[name]) else None
            if detail and facts[name].get("state") != "observed":
                shown = f"{shown} {_scalar(detail)}"
            lines.append(f"  {name.ljust(width)}  {shown}")
        for name, why in sorted(unavailable.items()):
            reason = (
                why.get("reason") or why.get("detail") or why.get("state") or why
                if isinstance(why, dict)
                else why
            )
            lines.append(f"  {name.ljust(width)}  UNAVAILABLE: {_scalar(reason)}")
        lines.append("")
    return "\n".join(lines)


def tabulate(headers: list[str], rows: list[list[str]], view: str) -> str:
    """Headers and rows as CSV or as a Markdown table. One writer for both
    the evidence views and the composed scenarios, so they cannot drift."""
    if view == "csv":
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
        return out.getvalue()
    if view != "md":
        raise ValueError(f"not a table view: {view}")

    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _csv(documents: list[dict]) -> str:
    return tabulate(*table(documents), "csv")


def _md(documents: list[dict]) -> str:
    return tabulate(*table(documents), "md")


def render(documents: list[dict], view: str) -> str:
    """The documents as `view`. JSON is the documents, untouched."""
    if view == "json":
        return json.dumps(documents, indent=2) + "\n"
    if view == "csv":
        return _csv(documents)
    if view == "md":
        return _md(documents)
    if view == "text":
        return _text(documents)
    raise ValueError(f"unknown view: {view}")
