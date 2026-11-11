"""Evidence, laid out for a terminal. A view, and never the evidence.

`m365g spo site list` answers in the terminal, and what it prints is this
module's rendering of the evidence documents the collection wrote. The
documents are the product: they carry provenance, coverage and the schema. A
view carries none of that and replaces none of it, which is why the JSON view
is the documents themselves and every other view is derived from them without
adding a word of its own.

NOTHING IS CONCLUDED HERE. A fact is shown with the state the collector gave
it, an unavailable fact is shown as unavailable, and nothing is counted as
good or bad: that is what rules are for. A count that does appear is the
length of a list the document holds, named for the list it counts.
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


def fact(value: Any) -> str:
    """One fact in one cell, in the collector's own words.

    The state comes first because it is what says whether the rest was
    observed. Scalars are shown as `name=value`; a list is shown as its name
    and how many entries it holds; a nested object as its name and its keys.
    """
    if not isinstance(value, dict):
        return (
            _scalar(value) if not isinstance(value, list) else f"{len(value)} entries"
        )
    parts = []
    if "state" in value:
        parts.append(_scalar(value["state"]))
    for key in sorted(k for k in value if k != "state"):
        inner = value[key]
        if isinstance(inner, list):
            parts.append(f"{key}: {len(inner)} entries")
        elif isinstance(inner, dict):
            parts.append(f"{key}: {{{', '.join(sorted(inner))}}}")
        else:
            parts.append(f"{key}={_scalar(inner)}")
    return "; ".join(parts)


def table(documents: list[dict]) -> tuple[list[str], list[list[str]]]:
    """Headers and rows for the documents: one row per resource."""
    names = sorted({name for doc in documents for name in doc.get("facts", {})})
    rows = []
    for doc in documents:
        resource = doc.get("resource", {})
        provenance = doc.get("provenance", {})
        coverage = doc.get("coverage", {})
        facts = doc.get("facts", {})
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
        lines.append(f"{title}  {where}".rstrip())
        lines.append(f"  {resource.get('type', '')} · {resource.get('native_id', '')}")
        facts = doc.get("facts", {})
        width = max((len(name) for name in facts), default=0)
        for name in sorted(facts):
            lines.append(f"  {name.ljust(width)}  {fact(facts[name])}")
        for name, why in sorted((coverage.get("unavailable") or {}).items()):
            reason = why.get("reason", why) if isinstance(why, dict) else why
            lines.append(f"  {name.ljust(width)}  UNAVAILABLE: {_scalar(reason)}")
        lines.append("")
    return "\n".join(lines)


def _csv(documents: list[dict]) -> str:
    headers, rows = table(documents)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return out.getvalue()


def _md(documents: list[dict]) -> str:
    headers, rows = table(documents)

    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


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
