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

IT IS NEVER A BARE VERDICT. Every judgement carries `because`: the observable
facts that produced it. A state with no reasons is exactly the thing this
product exists to stop shipping.

TWO VOCABULARIES, AND THEY ARE NOT THE SAME ONE.

    STATE   five values, and it is the grouping a reader is shown
    TIER    six values, and it is the published order

They differ because `observe` — the engine reaching no answer — happens for two
different reasons that must not be flattened: evidence read and not trusted, and
evidence never read. One state, two tiers.

THEY USED TO SHARE A DICTIONARY, and it was wrong in a way nothing caught. The
ranks were keyed by a mixture of state names (`act`, `review`, `none`,
`not-evaluated`) and outcome names (`invalid-evidence`, `unknown`), so `observe`
had no entry at all. A run in `observe` looked its rank up, missed, and fell
through to a default — publishing 2, which is `not-evaluated`'s rank. The
document said one thing in `state` and a different thing in `rank`, and both
looked deliberate.

So the two enumerations are now separate, and no name appears in both.

ABSENCE STAYS EXPLICIT, AND `none` IS NOT ABSENCE. `none` is a judgement: the
engine looked, decided, and nothing follows. It is counted like every other
state, because a state that vanished when it was empty would make "nothing to
do" and "nobody asked" the same reading. `not-evaluated` is the one that means
no judgement was formed.
"""

from __future__ import annotations

from typing import Any

#: The basis types that make a failure a documented violation rather than a
#: disagreement. A requirement and a documented limit are Microsoft's; guidance
#: is Microsoft's advice, a convention is a common practice, and an opinion is
#: ours. Failing the first two means the tenant is outside something written
#: down by the vendor; failing the others means somebody chose differently.
NORMATIVE = ("requirement", "documented-limit")

#: THE FIVE STATES. What a reader is shown, and the only vocabulary that
#: appears in `state`. Every one of them is counted, `none` included.
STATES = ("act", "review", "observe", "none", "not-evaluated")

#: THE SIX TIERS, in published order, and deliberately named so that not one of
#: them can be mistaken for a state. `rank` is the index of a tier.
#:
#: The principle is how far the report fails to describe the tenant, and how
#: much of that is a defect rather than a gap:
#:
#:   0  documented-violation   the tenant is outside something the vendor
#:                             wrote down
#:   1  evidence-untrusted     read, and not to be relied on. Above an absent
#:                             reading because a malformed value looks like
#:                             data, while an absence announces itself
#:   2  no-judgement           the evaluation produced nothing at all. HERE
#:                             and not last: it says nothing about the tenant,
#:                             which is exactly why somebody has to look, and
#:                             ranking it below a pass would bury a defect of
#:                             ours underneath good news
#:   3  evidence-absent        nobody read it. A gap rather than a defect, and
#:                             still above a decided non-normative matter,
#:                             because the product's whole claim is that
#:                             uncertainty stays visible
#:   4  decided-non-normative  decided, and a choice to weigh rather than a
#:                             violation
#:   5  settled                decided, and nothing follows
TIERS = (
    "documented-violation",
    "evidence-untrusted",
    "no-judgement",
    "evidence-absent",
    "decided-non-normative",
    "settled",
)

#: Which state a reader is shown for each tier. Many-to-one on purpose:
#: `observe` covers two tiers, and that is the whole reason the two
#: enumerations exist separately.
STATE_OF_TIER = {
    "documented-violation": "act",
    "evidence-untrusted": "observe",
    "no-judgement": "not-evaluated",
    "evidence-absent": "observe",
    "decided-non-normative": "review",
    "settled": "none",
}

#: The published integer for each tier: its position in `TIERS`.
RANK = {tier: index for index, tier in enumerate(TIERS)}

#: The tier a run enters when a requested area was never read. It is the same
#: tier as an unread result, because it is the same fact: part of the estate
#: was not observed, and everything else describes only the rest.
UNOBSERVED_TIER = "evidence-absent"


def _tier(result: dict) -> tuple[str, list[str]]:
    """One result's tier and the facts that put it there. Facts only."""
    outcome = result["outcome"]
    basis = result.get("basis", "")
    unresolved = (result.get("passes_without_resolving") or "").strip()

    if outcome == "error":
        # The evaluation itself failed. That is a sentence about the engine and
        # not about the tenant, so there is nothing here to rank — and saying
        # so is different from saying nothing is wrong.
        return "no-judgement", [
            "the evaluation did not complete, so this says nothing about the tenant"
        ]

    if outcome == "invalid-evidence":
        return "evidence-untrusted", [
            "the evidence was read and could not be trusted, so no answer rests on it"
        ]

    if outcome == "unknown":
        return "evidence-absent", [
            "the evidence needed to decide this was not available"
        ]

    if outcome == "fail":
        if basis in NORMATIVE:
            return "documented-violation", [
                f"the rule failed against a {basis}, which the vendor documents"
            ]
        return "decided-non-normative", [
            f"the rule failed against a {basis or 'basis that is not recorded'}, "
            "which is a choice to weigh rather than a documented violation"
        ]

    if outcome == "pass":
        if unresolved:
            return "decided-non-normative", [
                "it passed, and the rule records something the pass does not settle"
            ]
        return "settled", ["it passed and left nothing unresolved"]

    if outcome == "not-applicable":
        return "settled", ["the rule does not apply to this resource"]

    # An outcome nobody here knows. Ranking it would be inventing a meaning for
    # a string the contract has not defined yet.
    return "no-judgement", [f"`{outcome}` is not an outcome this engine ranks"]


def rank_of_outcome(outcome: str) -> int:
    """Where an outcome sits, for a report that groups by outcome.

    Asked of the same judgement a result gets, with a normative basis, so the
    grouping cannot drift from the ranking. It is a weaker question than
    `for_result` — a `fail` on a convention ranks differently from one on a
    requirement, and a group heading cannot express that — so the group takes
    the strongest attention its outcome can reach.
    """
    tier, _ = _tier(
        {"outcome": outcome, "basis": "requirement", "passes_without_resolving": ""}
    )
    return RANK[tier]


def for_result(result: dict) -> dict[str, Any]:
    """The attention block that travels with one result."""
    tier, because = _tier(result)
    return {"state": STATE_OF_TIER[tier], "rank": RANK[tier], "because": because}


def for_run(results: list[dict], coverage: dict) -> dict[str, Any]:
    """The attention a whole run carries.

    NOT A SUM OF THE RESULTS. A slice the collector could not read produces no
    result at all, so a run whose every rule passed can still be a run that saw
    almost nothing. Counting only results would report that as clean, which is
    the omission the coverage surface exists to prevent.

    ONE RULE, AND IT IS THE SAME ONE THE RESULTS USE: the run takes the most
    urgent tier present, counting an unread area as an unread reading. This was
    a ladder of `if` branches in which `observe` appeared TWICE, once above
    `not-evaluated` and once below it, so which of the two a run reported
    depended on whether its gap was an unread area or an unanswered rule. The
    order is a property of the tiers, and asking them is the way not to have a
    second copy of it.
    """
    tiers = [_tier(r)[0] for r in results]
    counts = {
        state: sum(1 for tier in tiers if STATE_OF_TIER[tier] == state)
        for state in STATES
    }

    unavailable = coverage.get("unavailable", {}) or {}

    # READ IN PART IS NOT UNREAD, AND THE SCREEN SAID IT WAS. `unobserved` is
    # documented as the areas the collector COULD NOT READ, and it was built
    # from every key of `unavailable` — so an area whose collector read half of
    # it and said so was published under the same name as one nobody touched.
    # A run with two partial areas and one missing one announced `3 areas were
    # not observed at all`, which is a stronger claim than the evidence makes,
    # in the direction this product exists to prevent.
    #
    # The tier does not move: part of the estate was still not observed either
    # way, and a partial reading that dropped out of the ranking would be the
    # same omission with the opposite sign. Only the sentence changes, and it
    # changes to the one that is true.
    unobserved = sorted(
        name
        for name, entry in unavailable.items()
        if (entry or {}).get("state") != "partial"
    )
    partial = sorted(
        name
        for name, entry in unavailable.items()
        if (entry or {}).get("state") == "partial"
    )

    present = [RANK[tier] for tier in tiers]
    if unavailable:
        present.append(RANK[UNOBSERVED_TIER])

    if not present:
        rank = RANK["no-judgement"]
        return {
            "state": STATE_OF_TIER["no-judgement"],
            "rank": rank,
            "because": ["no rule was evaluated against this resource"],
            "counts": counts,
            "unobserved": unobserved,
        }

    rank = min(present)
    leading = TIERS[rank]
    state = STATE_OF_TIER[leading]

    because = [_leading_reason(leading, counts, unobserved, partial, len(results))]

    # Said whatever the leading tier is: a run with failures AND unread areas
    # describes only the part that was observed, and the leading reason alone
    # would hide the second half of that sentence.
    if unavailable and leading != UNOBSERVED_TIER:
        because.append(
            _shortfall(unobserved, partial) + ", so this describes only what "
            "was observed"
        )

    return {
        "state": state,
        "rank": rank,
        "because": because,
        "counts": counts,
        "unobserved": unobserved,
    }


def _shortfall(unobserved: list[str], partial: list[str]) -> str:
    """What the collection fell short of, naming each shortfall as its own kind.

    TWO KINDS, NEVER ONE SENTENCE FOR BOTH. An area nobody read and an area read
    in part are different facts about the tenant, and the second is the weaker
    claim; saying `not read` for both overstates the gap, and dropping the
    partial ones understates it.
    """
    said = []
    if unobserved:
        said.append(
            f"{len(unobserved)} requested area(s) were not read: "
            + ", ".join(unobserved)
        )
    if partial:
        said.append(f"{len(partial)} were read only in part: " + ", ".join(partial))
    return "; ".join(said)


def _leading_reason(
    tier: str,
    counts: dict[str, int],
    unobserved: list[str],
    partial: list[str],
    total: int,
) -> str:
    """Why the run is where it is, in one sentence naming the facts."""
    if tier == "documented-violation":
        return (
            f"{counts['act']} of {total} findings failed against something "
            "the vendor documents"
        )
    if tier == "evidence-untrusted":
        return "evidence was read that could not be trusted"
    if tier == "no-judgement":
        return f"{counts['not-evaluated']} rule(s) produced no judgement at all"
    if tier == "evidence-absent":
        if unobserved or partial:
            return _shortfall(unobserved, partial)
        return f"{counts['observe']} finding(s) reached no answer"
    if tier == "decided-non-normative":
        return f"{counts['review']} finding(s) were decided and are worth weighing"
    return "every rule reached an answer and none of them failed"
