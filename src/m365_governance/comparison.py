"""What changed between two assessments, and nothing about why.

A COMPARISON RELATES TWO STATES AND BELONGS TO NEITHER. Putting a diff inside
an assessment would make one state carry an assertion about another, and the
assertion would then travel with an archive that cannot be re-derived from it.

IT NAMES THEM AND NEVER EMBEDS THEM. Each side is an `assessment_id` and a
canonical digest, which is identity that can be verified rather than trusted. A
comparison that carried both assessments would duplicate the canonical truth it
describes, and the duplicate would be the thing somebody edits.

IT IS DERIVED, SO IT IS REPRODUCIBLE. Given the same two assessments, this
produces the same bytes. Nothing is read from the clock and nothing is read
from the installation: the engine version that computed it is passed in and
recorded, because a diff nobody can reproduce is an opinion about history.

OBSERVATION AND ATTRIBUTION ARE SEPARATE FIELDS, and this module never fills
the second with the first. `changes` says what was observed to differ.
Attribution says who is responsible for it, and answering that when evidence
and a rule moved together needs a counterfactual evaluation — the old evidence
against the new rule — that nobody here ran. So nothing is ever `established`:
two or more candidates make it `ambiguous`, and everything else is
`not-evaluated`, which is a different sentence from "we looked and could not
tell".
"""

from __future__ import annotations

from typing import Any

from . import assessment as assessment_module
from . import diffing, registry
from .results import RunSet


class Incomparable(ValueError):
    """These two assessments cannot be compared, and saying why is the answer."""


def _side(document: dict, which: str) -> dict:
    problems = assessment_module.verify(document)
    if problems:
        raise Incomparable(
            f"the {which} assessment does not verify ({problems[0]}), so what "
            "it describes is not what it says it describes"
        )

    canonical = document["canonical"]
    manifest = canonical["manifest"]
    side = {
        "assessment_id": manifest["assessment_id"],
        "created_at": manifest["created_at"],
        "canonical_hash": canonical["hashes"]["canonical_hash"],
        "tenant": manifest["tenant"],
    }
    return side


def _attribution(moved: list[str]) -> dict:
    """Who is responsible, which is a question this engine does not answer.

    `established` needs a method, and the only method that would establish
    anything here is re-evaluating the older evidence against the newer rule.
    Nobody ran it, so nobody may claim it. Noticing that two things moved is not
    a method; it is the observation that makes the question hard.
    """
    candidates = [factor for factor in moved if factor != "outcome"]
    if len(candidates) > 1:
        return {"state": "ambiguous", "factors": sorted(candidates)}
    # One candidate is not a cause either. The outcome moved and so did one
    # other thing, and saying the second produced the first is exactly the
    # counterfactual nobody ran.
    return {"state": "not-evaluated"}


def _observed(change: diffing.RuleChange) -> list[str]:
    """What was observed to differ. Observed, and never why."""
    moved = []
    before = change.before.outcome.value if change.before else None
    after = change.after.outcome.value if change.after else None
    if before != after:
        moved.append("outcome")
    if change.rule_version_changed:
        moved.append("rule-version")
    if change.evidence:
        moved.append("evidence")
    return sorted(moved)


def _changes(before: dict, after: dict) -> list[dict[str, Any]]:
    """What moved, computed by the one implementation of moving.

    `diffing` already pairs resources and rules, notices a rule version that
    changed, and names the evidence that moved. Writing that again here would
    be a second answer to one question, kept in step by hand until the morning
    it was not — which is the defect this contract exists to remove elsewhere.

    So the run-level comparison stays, as an implementation detail. It is not a
    document anybody keeps and it claims no contract of its own.
    """
    pairs = diffing.compare_sets(
        RunSet.from_dict(before["canonical"]["run_set"]),
        RunSet.from_dict(after["canonical"]["run_set"]),
    )

    found: list[dict[str, Any]] = []
    for resource in pairs:
        for rule in resource.rules:
            moved = _observed(rule)
            if rule.kind == "changed" and not moved:
                continue

            change: dict[str, Any] = {
                "resource": dict(resource.resource_ref),
                "rule": rule.rule_id,
                "before": rule.before.outcome.value if rule.before else None,
                "after": rule.after.outcome.value if rule.after else None,
                "kind": rule.kind,
            }
            if rule.kind == "changed":
                change["changes"] = moved
                change["attribution"] = _attribution(moved)
            found.append(change)

    # Sorted, because a comparison of the same two assessments has to produce
    # the same bytes and dictionary order is not a guarantee anybody should
    # rely on for that.
    return sorted(found, key=lambda c: (c["resource"], c["rule"]))


def build(before: dict, after: dict, *, engine_version: str) -> dict:
    """One comparison of two assessments.

    Refuses two tenants: a comparison across estates would put changes nobody
    manages together into one list, and every count in it would be a sum across
    two organisations.
    """
    sides = {"before": _side(before, "before"), "after": _side(after, "after")}

    if sides["before"]["tenant"] != sides["after"]["tenant"]:
        raise Incomparable(
            "these assessments are about different tenants "
            f"({sides['before']['tenant']['host']} and "
            f"{sides['after']['tenant']['host']}), and a comparison relates two "
            "states of one estate"
        )
    # The same assessment twice is deliberately not an error. It is a
    # legitimate question with an empty answer, and producing that answer is
    # what proves the comparison is derived rather than assembled from
    # expectations about what should have moved.

    changes = _changes(before, after)

    return {
        "$schema": registry.contract("comparison"),
        "before": sides["before"],
        "after": sides["after"],
        "diff": {"produced_by": engine_version, "changes": changes},
    }
