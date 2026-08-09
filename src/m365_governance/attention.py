"""Whether a person has to look, and what made that true.

ATTENTION IS NOT THE OUTCOME. `fail` says a rule's condition was not met. It
does not say anybody must act: a rule whose basis is a convention reports
`fail` when a tenant made a defensible different choice, and a `pass` that
leaves something unresolved can still be the most interesting line on the page.
Reading the outcome as the verdict is how a report turns into a scoreboard.

ATTENTION IS NOT THE SEVERITY. Severity is the rule author's standing claim
about what is at stake IF the rule is violated. It is written once, against no
tenant, and it is the same string whether the evidence was read completely,
partially or not at all. Attention is about this reading of this tenant,
including the case where nothing was read — which severity cannot express,
because a rule that never ran still has one.

SO IT IS PUBLISHED HERE AND NOWHERE ELSE. A viewer that worked out what
deserves attention would be a second authority on governance: it agrees with
the engine until the day it does not, and then nobody can say which was right.
The Workbench ordered its findings `fail`, `invalid-evidence`, `unknown`,
`pass`, `not-applicable` — a governance priority, written in C#, that the CLI
never knew about. The two surfaces of one product disagreed about what
mattered, and each was internally consistent.

IT IS NEVER A BARE VERDICT. Every judgement carries `because`: the observable
facts that produced it. A state with no reasons is exactly the thing this
product exists to stop shipping.

ABSENCE STAYS EXPLICIT. `not-evaluated` is a real state and it is not `none`.
`none` says the engine looked and nothing follows; `not-evaluated` says the
engine formed no judgement at all. Collapsing them would make an unranked
result indistinguishable from a clean one.
"""

from __future__ import annotations

from typing import Any

#: The basis types that make a failure a documented violation rather than a
#: disagreement. A requirement and a documented limit are Microsoft's; guidance
#: is Microsoft's advice, a convention is a common practice, and an opinion is
#: ours. Failing the first two means the tenant is outside something written
#: down by the vendor; failing the others means somebody chose differently.
NORMATIVE = ("requirement", "documented-limit")

#: Every state, in the published order. The Workbench renders this; it does not
#: reproduce it.
STATES = ("act", "review", "observe", "none", "not-evaluated")

#: WHY THIS ORDER, since ordering carries governance meaning and therefore
#: belongs to the engine rather than to whoever is drawing the list.
#:
#: The principle is how far the report fails to describe the tenant, and how
#: much of that is a defect rather than a gap:
#:
#:   0  act                a documented violation: the tenant is outside
#:                         something the vendor wrote down
#:   1  invalid evidence   the engine read something it cannot trust. Above an
#:                         absent reading because a malformed value looks like
#:                         data, while an absence announces itself
#:   2  not-evaluated      no judgement was formed at all — the evaluation
#:                         broke, or the outcome is one this engine does not
#:                         rank. It sits HERE and not last: it says nothing
#:                         about the tenant, which is exactly why somebody has
#:                         to look, and ranking it below a pass would bury a
#:                         defect of ours underneath good news
#:   3  unknown            nobody read it. A gap rather than a defect, and
#:                         still above a decided non-normative matter, because
#:                         the product's whole claim is that uncertainty stays
#:                         visible
#:   4  review             the engine decided, and the matter is a choice to
#:                         weigh rather than a violation
#:   5  none               decided, and nothing follows
RANKS = {
    "act": 0,
    "invalid-evidence": 1,
    "not-evaluated": 2,
    "unknown": 3,
    "review": 4,
    "none": 5,
}


#: The order the CLI groups its report by, derived rather than written again.
#: The command line held its own list — fail, invalid-evidence, unknown, error,
#: not-applicable, pass — and the Workbench held a different one, in which pass
#: came BEFORE not-applicable and an engine error was nowhere. Two surfaces of
#: one product, each internally consistent, disagreeing about what mattered.
def rank_of_outcome(outcome: str) -> int:
    """Where an outcome sits, for a report that groups by outcome.

    Asked of the same judgement a result gets, with a normative basis, so the
    grouping cannot drift from the ranking. It is a weaker question than
    `for_result` — a `fail` on a convention ranks differently from one on a
    requirement, and a group heading cannot express that — so the group takes
    the strongest attention its outcome can reach.
    """
    return _judge(
        {"outcome": outcome, "basis": "requirement", "passes_without_resolving": ""}
    )[1]


def _judge(result: dict) -> tuple[str, int, list[str]]:
    """One result's state, rank and reasons. Facts only."""
    outcome = result["outcome"]
    basis = result.get("basis", "")
    unresolved = (result.get("passes_without_resolving") or "").strip()

    if outcome == "error":
        # The evaluation itself failed. That is a sentence about the engine and
        # not about the tenant, so there is nothing here to rank — and saying
        # so is different from saying nothing is wrong.
        return (
            "not-evaluated",
            RANKS["not-evaluated"],
            ["the evaluation did not complete, so this says nothing about the tenant"],
        )

    if outcome == "invalid-evidence":
        return (
            "observe",
            RANKS["invalid-evidence"],
            [
                "the evidence was read and could not be trusted, so no "
                "answer rests on it"
            ],
        )

    if outcome == "unknown":
        return (
            "observe",
            RANKS["unknown"],
            ["the evidence needed to decide this was not available"],
        )

    if outcome == "fail":
        if basis in NORMATIVE:
            return (
                "act",
                RANKS["act"],
                [f"the rule failed against a {basis}, which the vendor documents"],
            )
        return (
            "review",
            RANKS["review"],
            [
                f"the rule failed against a {basis or 'basis that is not recorded'}, "
                "which is a choice to weigh rather than a documented violation"
            ],
        )

    if outcome == "pass":
        if unresolved:
            return (
                "review",
                RANKS["review"],
                ["it passed, and the rule records something the pass does not settle"],
            )
        return "none", RANKS["none"], ["it passed and left nothing unresolved"]

    if outcome == "not-applicable":
        return "none", RANKS["none"], ["the rule does not apply to this resource"]

    # An outcome nobody here knows. Ranking it would be inventing a meaning for
    # a string the contract has not defined yet.
    return (
        "not-evaluated",
        RANKS["not-evaluated"],
        [f"`{outcome}` is not an outcome this engine ranks"],
    )


def for_result(result: dict) -> dict[str, Any]:
    """The attention block that travels with one result."""
    state, rank, because = _judge(result)
    return {"state": state, "rank": rank, "because": because}


def for_run(results: list[dict], coverage: dict) -> dict[str, Any]:
    """The attention a whole run carries.

    NOT A SUM OF THE RESULTS. A slice the collector could not read produces no
    result at all, so a run whose every rule passed can still be a run that saw
    almost nothing. Counting only results would report that as clean, which is
    the omission the coverage surface exists to prevent.
    """
    states = [for_result(r)["state"] for r in results]
    counts = {state: states.count(state) for state in STATES}

    unavailable = coverage.get("unavailable", {}) or {}
    unobserved = sorted(unavailable)

    because: list[str] = []
    if counts["act"]:
        state = "act"
        because.append(
            f"{counts['act']} of {len(results)} findings failed against something "
            "the vendor documents"
        )
    elif unobserved:
        # Ahead of `review`, because a gap in what was read is a statement about
        # the report itself: everything else on the page describes only the part
        # that was observed.
        state = "observe"
        because.append(
            f"{len(unobserved)} requested area(s) were not read: "
            + ", ".join(unobserved)
        )
    elif counts["not-evaluated"]:
        # Above `observe` and `review` for the same reason it outranks them per
        # result: a rule that never produced a judgement is a defect of ours,
        # and it must not sit underneath findings that did.
        state = "not-evaluated"
        because.append(
            f"{counts['not-evaluated']} rule(s) produced no judgement at all"
        )
    elif counts["observe"]:
        state = "observe"
        because.append(f"{counts['observe']} finding(s) reached no answer")
    elif counts["review"]:
        state = "review"
        because.append(
            f"{counts['review']} finding(s) were decided and are worth weighing"
        )
    elif results:
        state = "none"
        because.append("every rule reached an answer and none of them failed")
    else:
        state = "not-evaluated"
        because.append("no rule was evaluated against this resource")

    # Said whatever the leading state is: a run with failures AND unread areas
    # describes only the part that was observed, and the leading state alone
    # would hide the second half of that sentence.
    if unobserved and state != "observe":
        because.append(
            f"{len(unobserved)} requested area(s) were also not read, so this "
            "describes only what was observed"
        )

    return {
        "state": state,
        "rank": RANKS[state] if state in RANKS else RANKS["not-evaluated"],
        "because": because,
        "counts": counts,
        "unobserved": unobserved,
    }
