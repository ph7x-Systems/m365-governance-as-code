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
READ = "migration-read"

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


#: What a gap in coverage does to a finding. It is the whole behaviour of this
#: module in one line: an item that could not be read has not been shown to be
#: missing, so absence of evidence never becomes evidence of absence.
COVERED_BY_A_GAP = "unknown"


class Unverifiable(ValueError):
    """This record cannot be produced, and saying why is the answer."""


def contract() -> str:
    """The exact contract a producer of these documents must declare."""
    return registry.contract(NAME)


def read_contract() -> str:
    """The exact contract a read must declare, which is what we ask for."""
    return registry.contract(READ)


def reference(read: dict) -> dict:
    """A read, as the verification record names it.

    By identity and digest rather than by copy. The record stays small, the
    reads stay authoritative, and anyone holding both can recompute the whole
    thing — which is the only reason a third party can check this without us.

    Coverage is carried across rather than referenced, because a reader
    deciding how much weight to give a finding needs to see what could not be
    read without fetching a second document.
    """
    return {
        "read_id": read["read_id"],
        "taken_at": read["taken_at"],
        "estate": read["estate"],
        "canonical_hash": canonical.digest(read),
        "coverage": read.get("coverage", []),
    }


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


# ---------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------
#
# TWO READS IN, FINDINGS OUT, AND NOTHING FROM THE CLOCK OR THE INSTALLATION.
# The same two reads produce the same findings in the same order on any
# machine, which is what lets a third party recompute this without us.
#
# THE ONE RULE WORTH READING THE CODE FOR. A difference only becomes `fail`
# when both sides were actually readable. If either read declared a gap
# covering the item, the honest outcome is `unknown` — and this is where every
# migration report goes wrong, because reporting an item as missing is more
# useful-sounding than reporting that nobody could look.


def _covered(coverage: list[dict], item: str) -> dict | None:
    """The gap that swallows this item, if a read declared one.

    Prefix matching, because gaps are declared over containers and items live
    inside them. A gap on `/Shared Documents/Archive` covers everything under
    it, which is exactly what the person who could not read it meant.
    """
    for gap in coverage:
        scope = gap.get("scope", "")
        if item == scope or item.startswith(scope.rstrip("/") + "/"):
            return gap
    return None


def _unreadable(baseline: dict, verification: dict, item: str) -> dict | None:
    """Which side could not see this item, as a finding fragment.

    `both` is not a formality. An item inside a gap on each side is less
    established than one inside a gap on either, and a reader deciding whether
    to go and look themselves needs to know which.
    """
    before = _covered(baseline.get("coverage", []), item)
    after = _covered(verification.get("coverage", []), item)
    if not before and not after:
        return None
    if before and after:
        side, gap = "both", before
    elif before:
        side, gap = "baseline", before
    else:
        side, gap = "verification", after
    return {"side": side, "state": gap["state"], "detail": gap.get("detail")}


def _finding(item: str, dimension: str, outcome: str, **rest) -> dict:
    finding = {"item": item, "dimension": dimension, "outcome": outcome}
    finding.update({k: v for k, v in rest.items() if v is not None})
    return finding


def _presence(baseline: dict, verification: dict) -> list[dict]:
    before = set(baseline.get("items", {}))
    after = set(verification.get("items", {}))
    findings = []
    for item in sorted(before | after):
        gap = _unreadable(baseline, verification, item)
        if item in before and item in after:
            continue  # present on both sides; nothing to say
        if gap:
            findings.append(
                _finding(item, "presence", COVERED_BY_A_GAP, **gap)
            )
            continue
        findings.append(
            _finding(
                item,
                "presence",
                "fail",
                observed={
                    "baseline": item in before,
                    "verification": item in after,
                },
            )
        )
    return findings


#: Which attribute each dimension reads off an item. `presence` is absent
#: because it is about the item rather than about anything on it.
ATTRIBUTE = {
    "size": "size",
    "content": "content_digest",
    "authorship": "author",
    "versions": "versions",
    "permissions": "permissions",
    "sharing-links": "sharing_links",
}


def _attribute(
    baseline: dict, verification: dict, dimension: str, method: str | None
) -> list[dict]:
    key = ATTRIBUTE[dimension]
    before = baseline.get("items", {})
    after = verification.get("items", {})
    findings = []
    for item in sorted(set(before) & set(after)):
        gap = _unreadable(baseline, verification, item)
        if gap:
            findings.append(_finding(item, dimension, COVERED_BY_A_GAP, **gap))
            continue

        if dimension == "content" and method == WEIGHED_NOT_READ:
            # Decided by the method before anything is read. A size-only
            # comparison has no digest by definition, so reporting a thin read
            # here would blame the data for the choice the operator made.
            findings.append(
                _finding(
                    item,
                    dimension,
                    COVERED_BY_A_GAP,
                    side="both",
                    state="partial",
                    method=method,
                    detail="compared by size alone; content was not hashed",
                )
            )
            continue

        seen_before = _comparable(before[item].get(key))
        seen_after = _comparable(after[item].get(key))
        if seen_before is None or seen_after is None:
            # Neither read declared a gap and the attribute is still not there.
            # That is the read being thinner than it claimed, and saying so is
            # more useful than either verdict.
            findings.append(
                _finding(
                    item,
                    dimension,
                    COVERED_BY_A_GAP,
                    side="baseline" if seen_before is None else "verification",
                    state="partial",
                    detail=f"the read carries no {key} for this item",
                )
            )
            continue

        if seen_before == seen_after:
            continue

        findings.append(
            _finding(
                item,
                dimension,
                "fail",
                method=method,
                observed={"baseline": seen_before, "verification": seen_after},
            )
        )
    return findings


#: Attributes that are sets wearing a list's clothes. Two grants in a different
#: order are the same two grants, and a report that called that a change would
#: be noise on the one dimension where noise is most expensive: nobody reads
#: the permission findings twice after the first false alarm.
SET_LIKE = ("permissions", "sharing_links")


def _comparable(value: Any) -> Any:
    """The value as it should be compared, and as it is recorded.

    Sorting here rather than trusting the producer to sort: a rule that depends
    on every future collector remembering it is a rule that holds until the
    second collector.
    """
    if isinstance(value, list):
        return sorted(value, key=canonical.encode)
    return value


def _count(baseline: dict, verification: dict) -> list[dict]:
    """How many items each side holds, and only when both were fully read.

    A count is a claim about a whole container, so a single gap anywhere
    invalidates it. The first version reported `fail` for an estate whose only
    difference was a folder nobody could open — contradicting, in the same
    document, the `unknown` it had just recorded for the items inside it.
    """
    gaps = baseline.get("coverage", []) + verification.get("coverage", [])
    before = len(baseline.get("items", {}))
    after = len(verification.get("items", {}))
    if before == after and not gaps:
        return []
    if gaps:
        first = (baseline.get("coverage") or verification.get("coverage"))[0]
        return [
            _finding(
                "<estate>",
                "count",
                COVERED_BY_A_GAP,
                side="baseline" if baseline.get("coverage") else "verification",
                state=first["state"],
                detail="a count is a claim about the whole estate, and part of "
                f"it could not be read ({first['scope']})",
            )
        ]
    return [
        _finding(
            "<estate>",
            "count",
            "fail",
            observed={"baseline": before, "verification": after},
        )
    ]


def compare(*, baseline: dict, verification: dict, dimensions: list[dict]) -> list[dict]:
    """Findings for every declared dimension, and none for any other.

    A dimension declared `not-compared` produces nothing, which is the only
    behaviour consistent with saying nobody looked.
    """
    findings: list[dict] = []
    for declared in dimensions:
        if declared.get("state") != "compared":
            continue
        name = declared["name"]
        if name == "presence":
            findings.extend(_presence(baseline, verification))
        elif name == "count":
            findings.extend(_count(baseline, verification))
        elif name in ATTRIBUTE:
            findings.extend(
                _attribute(baseline, verification, name, declared.get("method"))
            )
    return findings


def dimensions_for(baseline: dict, verification: dict) -> list[dict]:
    """What these two reads can actually be compared on.

    DERIVED FROM THE EVIDENCE, NEVER ASSERTED BY THE CALLER. A flag saying
    `compare content by digest` would let somebody claim a comparison the reads
    cannot support, and the claim would be indistinguishable from a real one in
    the record. Here the reads decide: if both carry digests, content is
    compared by digest; if they carry sizes and no digests, it is `size-only`
    and the record says so; if they carry neither, content is not compared at
    all and the reason is written down.
    """
    before = baseline.get("items", {})
    after = verification.get("items", {})
    shared = set(before) & set(after)

    def carried(key: str) -> bool:
        return any(before[i].get(key) is not None for i in shared) and any(
            after[i].get(key) is not None for i in shared
        )

    dimensions = [
        {"name": "presence", "state": "compared"},
        {"name": "count", "state": "compared"},
    ]

    if carried("content_digest"):
        dimensions.append({"name": "content", "state": "compared", "method": "digest"})
    elif carried("size"):
        dimensions.append(
            {"name": "content", "state": "compared", "method": WEIGHED_NOT_READ}
        )
    else:
        dimensions.append(
            {
                "name": "content",
                "state": "not-compared",
                "reason": "neither read carries a digest or a size for the "
                "items they share",
            }
        )

    for name, key in (
        ("size", "size"),
        ("authorship", "author"),
        ("versions", "versions"),
        ("permissions", "permissions"),
        ("sharing-links", "sharing_links"),
    ):
        if carried(key):
            dimensions.append({"name": name, "state": "compared"})
        else:
            dimensions.append(
                {
                    "name": name,
                    "state": "not-compared",
                    "reason": f"at least one read carries no {key} for the "
                    "items they share",
                }
            )
    return dimensions


def record(*, baseline: dict, verification: dict, move: dict) -> dict:
    """Two reads in, a verification record out. The whole product in one call."""
    dimensions = dimensions_for(baseline, verification)
    return build(
        baseline=reference(baseline),
        verification=reference(verification),
        move=move,
        dimensions=dimensions,
        findings=compare(
            baseline=baseline, verification=verification, dimensions=dimensions
        ),
    )
