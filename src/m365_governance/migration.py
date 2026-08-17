"""What a move actually moved, established against a read taken before it.

A MIGRATION CANNOT BE VERIFIED AFTER THE FACT. Decommissioning the source is
the point of the exercise, so a record produced at sign-off has nothing left to
compare against. Everything here follows from that: the document always names
two reads of the same estate, the earlier one is the baseline, and a baseline
taken after the move is not a baseline — it is a second look at the
destination.

IT IS NEVER PRODUCED BY WHATEVER PERFORMED THE MOVE. A migration tool's report
is the producer's account of its own work, and no amount of detail changes what
it is. `performed_by` is recorded precisely so a reader can see that it is not
the party that wrote this.

THE FIVE STATES CARRY OVER UNCHANGED, and `unknown` is the whole difference. A
path too long to read, a file checked out, a principal that would not resolve:
each is a stated limitation. Never a silent pass, and — this is the half people
get wrong — never a failure either. An item that could not be read on one side
has not been shown to be missing.

SIZE IS NOT CONTENT. Two files of equal size differ. A comparison that only
weighed them may report anything except that the content matched, and
`_content_rule` refuses the document rather than trusting a caller to remember.

NO SCORE, NO PERCENTAGE, NO GRADE. `96% migrated` is what a reader substitutes
for eight dimensions the moment one is offered, and the substitution is what
destroys the record. There is nothing here to aggregate, deliberately.
"""

from __future__ import annotations

from typing import Any

from . import canonical, registry

NAME = "migration-verification"

#: What can be compared between two reads. The order is the order they are
#: worth doing in: presence before count, count before anything about the items
#: themselves, permissions last because that is where the reading is hardest.
DIMENSIONS = (
    "presence",
    "count",
    "size",
    "content",
    "authorship",
    "versions",
    "permissions",
    "sharing-links",
)

#: The dimension where how you looked decides what you may conclude.
WEIGHED_NOT_READ = "size-only"


class Unverifiable(ValueError):
    """This record cannot be produced, and saying why is the answer."""


def contract() -> str:
    """The exact contract a producer of these documents must declare."""
    return registry.contract(NAME)


def build(
    *,
    baseline: dict,
    verification: dict,
    move: dict,
    dimensions: list[dict],
    findings: list[dict],
) -> dict:
    """A verification record, refused rather than produced when incoherent.

    The caller supplies both reads by identity. Nothing is read from the clock:
    a record that changed depending on when it was written could not be
    reproduced, and reproducibility is the only reason a third party can check
    it without us.
    """
    document = {
        "$schema": contract(),
        "baseline": baseline,
        "verification": verification,
        "move": move,
        "dimensions": dimensions,
        "findings": findings,
    }
    problems = verify(document)
    if problems:
        raise Unverifiable(problems[0])
    return document


def digest(document: dict) -> str:
    """The record's canonical digest, in the form a consumer reproduces."""
    return canonical.digest(document)


def verify(document: dict, *, schemas: Any = None) -> list[str]:
    """What is wrong with this record, contract first and then coherence.

    The schema decides the shape of one object at a time. Everything below
    relates two of them, which JSON Schema cannot express and which is where
    the meaning lives.
    """
    problems: list[str] = []
    if schemas is not None:
        problems.extend(schemas.problems(document))
        if problems:
            return problems

    problems.extend(_ordering_rule(document))
    problems.extend(_distinct_reads_rule(document))
    problems.extend(_declared_dimension_rule(document))
    problems.extend(_content_rule(document))
    return problems


def _ordering_rule(document: dict) -> list[str]:
    """The baseline comes first, and this is the product's central rule.

    A read taken after the move cannot establish what was there before it. A
    document that put them the other way round would look identical and mean
    nothing, which is exactly why it is checked rather than assumed.
    """
    before = document.get("baseline", {}).get("taken_at")
    after = document.get("verification", {}).get("taken_at")
    if not before or not after:
        return []
    if before >= after:
        return [
            f"the baseline was taken at {before} and the verification at "
            f"{after}, so the baseline is not earlier than the move it is "
            "meant to precede. A migration cannot be verified against a read "
            "taken after it: that is a second look at the destination"
        ]
    return []


def _distinct_reads_rule(document: dict) -> list[str]:
    """Two reads, not one counted twice.

    A record comparing a read against itself passes every dimension and
    establishes nothing, and it is the most flattering document this contract
    could accidentally produce.
    """
    before = document.get("baseline", {})
    after = document.get("verification", {})
    if before.get("canonical_hash") and before.get("canonical_hash") == after.get(
        "canonical_hash"
    ):
        return [
            "both sides carry the same canonical digest, so this compares one "
            "read against itself. It would pass everything and establish "
            "nothing"
        ]
    return []


def _declared_dimension_rule(document: dict) -> list[str]:
    """Nothing is reported on a dimension that was not compared.

    Both directions are wrong in the same way. A finding on an undeclared
    dimension is a claim the document's own scope denies; a finding on one
    declared `not-compared` is worse, because the scope explicitly says nobody
    looked.
    """
    declared = {
        entry["name"]: entry.get("state")
        for entry in document.get("dimensions", [])
        if isinstance(entry, dict) and "name" in entry
    }
    problems = []
    for finding in document.get("findings", []):
        name = finding.get("dimension")
        if name not in declared:
            problems.append(
                f"{finding.get('item')}: reports on {name}, which this record "
                "does not declare among the dimensions it compared"
            )
        elif declared[name] == "not-compared":
            problems.append(
                f"{finding.get('item')}: reports on {name}, which this record "
                "declares was not compared. One of the two statements is false"
            )
    return problems


def _content_rule(document: dict) -> list[str]:
    """Weighing a file is not reading it.

    The schema catches the case where a finding names its own method. This
    catches the one where it inherits the dimension's, which is the ordinary
    case and therefore the one that would slip through.
    """
    declared = next(
        (
            entry
            for entry in document.get("dimensions", [])
            if isinstance(entry, dict) and entry.get("name") == "content"
        ),
        None,
    )
    if not declared or declared.get("method") != WEIGHED_NOT_READ:
        return []

    problems = []
    for finding in document.get("findings", []):
        if finding.get("dimension") != "content":
            continue
        method = finding.get("method", declared.get("method"))
        if method == WEIGHED_NOT_READ and finding.get("outcome") == "pass":
            problems.append(
                f"{finding.get('item')}: content is reported as matching, but "
                "it was compared by size alone. Two files of equal size "
                "differ, so the strongest available statement is `unknown`"
            )
    return problems
