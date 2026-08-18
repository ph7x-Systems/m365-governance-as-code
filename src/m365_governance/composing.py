"""One resource, however many collectors described it.

THE PIPELINE DID NOT COMPOSE, AND THE PRODUCT IS THE PIPELINE. `collect` writes
one evidence document per slice, because a slice is one question asked of one
surface. `assess` builds a run set, and a run set holds one run per resource,
because two runs about the same site would count that site twice. Between those
two correct decisions there was nothing: collecting `owners` and `sharing` for a
site produced two documents about one resource, and `assess` refused them with
`a run set describes the same resource twice`.

Found by running the product against a real tenant on 2026-08-18. Nine slices
collected cleanly and the assessment could not be built from them. The only way
through was to merge the documents by hand, which is the one thing the pipeline
is supposed to remove: evidence edited between the command that produced it and
the command that reads it is evidence nobody can verify.

WHAT THIS DOES, AND WHAT IT REFUSES. Documents describing the same resource are
composed into one: the union of their facts, and the union of what each says it
covered. Nothing is reconciled, averaged or preferred, because there is no
honest rule for that: two collectors reporting the same fact differently is a
defect in a collector, and this refuses rather than picks a winner.

WHAT IT DOES NOT TOUCH. The composed document is for evaluation. The assessment
still carries the ORIGINAL documents, each with its own provenance, so a
recipient verifies the bytes a collector wrote rather than something assembled
on the way past.
"""

from __future__ import annotations

from typing import Any

from . import identity


class Conflict(Exception):
    """Two documents about one resource disagree about what was collected."""


def compose(documents: list[dict]) -> list[dict]:
    """Evidence documents, one per resource, in the order they arrived.

    A resource described once comes back untouched. A resource described by
    several documents comes back once, carrying every fact and every coverage
    claim they made.
    """
    order: list[tuple] = []
    grouped: dict[tuple, list[dict]] = {}
    for document in documents:
        key = identity.key(document.get("resource", {}))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(document)

    return [
        grouped[key][0] if len(grouped[key]) == 1 else _one(grouped[key])
        for key in order
    ]


def _one(documents: list[dict]) -> dict:
    """Several documents about one resource, as one document."""
    composed = dict(documents[0])
    composed["facts"] = _facts(documents)
    composed["coverage"] = _coverage(documents)
    return composed


def _facts(documents: list[dict]) -> dict[str, Any]:
    """The union of every fact block, refusing a namespace claimed twice.

    Slices write into their own namespace -- `owners`, `sharing`, `spfx` -- so
    a collision is not two views of one thing. It is the same collector run
    twice, or two collectors that disagree about who owns a name, and either
    way a merge would publish one of them and hide the other.
    """
    facts: dict[str, Any] = {}
    source: dict[str, str] = {}
    for document in documents:
        where = _where(document)
        for name, block in (document.get("facts") or {}).items():
            if name in facts:
                # EVEN WHEN THEY MATCH. Identical blocks mean the same evidence
                # was supplied twice, and composing it silently would take one
                # and drop the other -- which is fine only if they really are
                # the same, and nobody here can promise the caller meant that.
                same = "identically" if block == facts[name] else "differently"
                raise Conflict(
                    f"{_readable(document)}: two evidence documents describe "
                    f"`{name}` {same} ({source[name]} and {where}). One of them "
                    f"would be ignored. Collect again rather than supplying "
                    f"both."
                )
            facts[name] = block
            source[name] = where
    return facts


def _coverage(documents: list[dict]) -> dict[str, Any]:
    """What the documents together say they covered.

    `requested` and `completed` are unions because each slice asked for its own
    and answered its own. `unavailable` is merged whole: an absence one
    collector recorded is not cancelled by another collector succeeding at
    something else.
    """
    requested: list[str] = []
    completed: list[str] = []
    unavailable: dict[str, Any] = {}
    for document in documents:
        coverage = document.get("coverage") or {}
        for name in coverage.get("requested") or []:
            if name not in requested:
                requested.append(name)
        for name in coverage.get("completed") or []:
            if name not in completed:
                completed.append(name)
        unavailable.update(coverage.get("unavailable") or {})
    return {
        "requested": requested,
        "completed": completed,
        "unavailable": unavailable,
    }


def _where(document: dict) -> str:
    provenance = document.get("provenance") or {}
    return str(provenance.get("collected_at") or provenance.get("collector") or "?")


def _readable(document: dict) -> str:
    return identity.readable(document.get("resource", {}))
