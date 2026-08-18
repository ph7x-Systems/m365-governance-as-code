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

import re
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
        "evidence_hash": canonical.digest([read.get("items"), read.get("coverage")]),
        "coverage": read.get("coverage", []),
        "read_by": read["read_by"],
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
    problems.extend(_same_eyes_rule(document))
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


def _same_eyes_rule(document: dict) -> list[str]:
    """Two reads taken by different identities are not comparable.

    AN ESTATE READ BY SOMEBODY WHO CANNOT SEE ALL OF IT IS BYTE-IDENTICAL TO A
    SMALLER ESTATE. Nothing refuses, so nothing writes a gap: the items are
    simply absent. Compare an administrator's baseline against an ordinary
    user's verification and every item the second could not see reports as
    missing — the most damaging thing this product could say, and it would say
    it with a clean coverage list.

    Refused rather than reported, because there is no finding that repairs it.
    Every `presence` result in such a record is unsound, and a document whose
    every row may be wrong is not a document with a caveat.
    """
    before = document.get("baseline", {}).get("read_by", {})
    after = document.get("verification", {}).get("read_by", {})
    if not before or not after:
        return []

    problems = []
    if before.get("principal") != after.get("principal"):
        # The two names come out first. Splitting a replacement field across
        # lines inside an f-string is 3.12 syntax, and this package supports
        # 3.11: written that way the module did not parse there at all.
        um = before.get("principal") or "an unnamed identity"
        outro = after.get("principal") or "an unnamed identity"
        problems.append(
            f"the baseline was read as {um} and the verification as {outro}. "
            "What one identity cannot see is absent rather than refused, so "
            "every missing item here may be a permission difference wearing "
            "the clothes of a loss"
        )
    if sorted(before.get("scopes", [])) != sorted(after.get("scopes", [])):
        problems.append(
            "the two reads were taken with different scopes ("
            + ", ".join(
                sorted(set(before.get("scopes", [])) ^ set(after.get("scopes", [])))
            )
            + "), so they did not have the same estate available to them"
        )
    return problems


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
            findings.append(_finding(item, "presence", COVERED_BY_A_GAP, **gap))
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


def compare(
    *, baseline: dict, verification: dict, dimensions: list[dict]
) -> list[dict]:
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

    #: What a source says it cannot do, as opposed to what a run did not do.
    unsupported = set(baseline.get("unsupported", [])) | set(
        verification.get("unsupported", [])
    )

    def absent(name: str, key: str) -> dict:
        """Why a dimension was not compared, kept as three distinct sentences.

        The distinction is the whole point and it cannot be inferred: a read
        with no `author` looks identical whether the surface never exposes
        authorship or whether this run did not ask. One is permanent and one is
        a fixable gap, and collapsing them is how a verification product starts
        reporting structural limits as execution failures.
        """
        if name in unsupported:
            return {
                "name": name,
                "state": "not-compared",
                "limit": "not-supported",
                "reason": f"the source declares it cannot provide {name}; "
                "reading again will not change that",
            }
        return {
            "name": name,
            "state": "not-compared",
            "limit": "not-carried",
            "reason": f"at least one read carries no {key} for the items they "
            "share, though the source is not declared unable to provide it",
        }

    #: A digest is only a digest against the same algorithm. Two reads hashed
    #: differently would compare unequal on every item, and every one of those
    #: would be a false report of a change that did not happen.
    algorithms = {
        baseline.get("content_digest_algorithm"),
        verification.get("content_digest_algorithm"),
    }

    if (
        "content" not in unsupported
        and carried("content_digest")
        and len(algorithms) > 1
    ):
        dimensions.append(
            {
                "name": "content",
                "state": "not-compared",
                "limit": "not-carried",
                "reason": "the two reads hashed with different algorithms ("
                + ", ".join(sorted(str(a) for a in algorithms))
                + "), and digests are only comparable against the same one",
            }
        )
    elif "content" not in unsupported and carried("content_digest"):
        dimensions.append({"name": "content", "state": "compared", "method": "digest"})
    elif "content" not in unsupported and carried("size"):
        dimensions.append(
            {"name": "content", "state": "compared", "method": WEIGHED_NOT_READ}
        )
    else:
        dimensions.append(absent("content", "digest or size"))

    for name, key in (
        ("size", "size"),
        ("authorship", "author"),
        ("versions", "versions"),
        ("permissions", "permissions"),
        ("sharing-links", "sharing_links"),
    ):
        if name not in unsupported and carried(key):
            dimensions.append({"name": name, "state": "compared"})
        else:
            dimensions.append(absent(name, key))
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


# ---------------------------------------------------------------------------
# the readable report
# ---------------------------------------------------------------------------
#
# THE RECORD IS THE EVIDENCE; THIS IS THE DOCUMENT. Neither replaces the other:
# the record is what a third party recomputes, and nobody recomputes anything
# from prose.
#
# THE SUMMARY HAS NO NUMBER IN IT THAT COULD BE READ AS A GRADE. Counts, yes —
# how many differences, how many things nobody could establish. A ratio, never.
# The moment a reader can say "94% fine" the six sections below stop being read,
# and the sections are the product.
#
# EVERY SECTION CAN BE EMPTY AND SAYS SO IN WORDS. A report whose empty parts
# vanish reads as though they never applied, and "nothing could not be
# verified" is a strong claim that has to be made out loud to be checked.

#: What each dimension means to somebody who did not write the schema.
IN_ENGLISH = {
    "presence": "the item is there at all",
    "count": "how many items the estate holds",
    "size": "the byte size of the item",
    "content": "the contents of the item",
    "authorship": "who the item says created it",
    "versions": "how much version history came across",
    "permissions": "who can reach the item",
    "sharing-links": "the sharing links that pointed at it",
}

#: How an absence reads in a sentence rather than as an enum value.
BECAUSE = {
    "missing": "it was not there to read",
    "not-supported": "the surface does not expose it",
    "permission-denied": "the reading identity was refused",
    "partial": "only part of it could be read",
}

#: How each side reads when the sentence needs a noun rather than a label.
SIDE = {
    "baseline": "before",
    "verification": "after",
    "both": "before and after",
}


def report(document: dict, fmt: str = "markdown") -> str:
    """The record as a document somebody can act on.

    Two formats, one source. HTML is rendered from the same lines rather than
    written separately: two renderers drift, and the day they do, one of them
    tells a client something the record does not say.

    Deterministic, like everything else here: the same record renders the same
    bytes, so the report can be digested and delivered alongside the evidence
    rather than regenerated and hoped over.
    """
    out: list[str] = []
    baseline, verification = document["baseline"], document["verification"]
    findings = document["findings"]

    by_outcome: dict[str, list[dict]] = {}
    for finding in findings:
        by_outcome.setdefault(finding["outcome"], []).append(finding)
    differences = by_outcome.get("fail", [])
    unestablished = by_outcome.get("unknown", [])

    compared = [d for d in document["dimensions"] if d["state"] == "compared"]
    skipped = [d for d in document["dimensions"] if d["state"] != "compared"]
    gaps = baseline["coverage"] + verification["coverage"]

    out.append(f"# Migration verification: {baseline['estate']}")
    out.append("")

    # -- executive summary ------------------------------------------------
    out.append("## Executive summary")
    out.append("")
    out.append(
        f"The estate was read on {baseline['taken_at']}, before the move, and "
        f"again on {verification['taken_at']}. This report compares those two "
        "reads. It was not produced by whatever performed the move."
    )
    out.append("")
    if baseline.get("evidence_hash") == verification.get("evidence_hash"):
        out.append(
            "**The two reads observed byte-identical estates.** Their ids and "
            "timestamps differ; what they saw does not. This report cannot "
            "tell whether the estate genuinely did not change or whether one "
            "observation was submitted twice, and it does not guess — the "
            "evidence digests are published below so a reader can see it for "
            "themselves. Across a real move, identical observations are not a "
            "quiet estate."
        )
        out.append("")

    if differences:
        out.append(
            f"**{len(differences)} difference(s) were established** between the "
            "two reads."
        )
    else:
        out.append(
            "**No differences were established** on the dimensions compared, "
            "within the limits below."
        )
    if unestablished:
        out.append("")
        out.append(
            f"**{len(unestablished)} thing(s) could not be established either "
            "way.** They are not differences and they are not confirmations: "
            "nobody was able to look. They are listed in full below, and a "
            "reader who needs them settled has to go and read what could not "
            "be read here."
        )
    out.append("")
    out.append(
        "There is no percentage in this report, deliberately. A single number "
        "would be read instead of the sections, and the sections are what "
        "answers the question."
    )
    out.append("")

    # -- what was verified ------------------------------------------------
    out.append("## What was verified")
    out.append("")
    if compared:
        out.append("These were compared across both reads:")
        out.append("")
        for entry in compared:
            how = f" (by {entry['method']})" if entry.get("method") else ""
            out.append(f"- **{entry['name']}**{how}: {IN_ENGLISH[entry['name']]}")
    else:
        out.append("Nothing was compared, which makes this report an inventory.")
    out.append("")

    # -- what could not be verified ---------------------------------------
    out.append("## What could not be verified")
    out.append("")
    if not skipped and not gaps and not unestablished:
        out.append(
            "Nothing. Both reads reached the whole declared estate, and every "
            "compared dimension returned an answer."
        )
    if skipped:
        out.append("Not compared at all:")
        out.append("")
        for entry in skipped:
            out.append(f"- **{entry['name']}**: {entry['reason']}")
        out.append("")
    if gaps:
        out.append("Not reachable by the reads:")
        out.append("")
        for gap in gaps:
            because = BECAUSE.get(gap["state"], gap["state"])
            out.append(
                f"- **{gap['scope']}**: {because}"
                + (f", because {gap['detail']}." if gap.get("detail") else ".")
            )
        out.append("")
    if unestablished:
        out.append("Compared, but not established for these items:")
        out.append("")
        for finding in unestablished:
            out.append(
                f"- `{finding['item']}` — {IN_ENGLISH[finding['dimension']]}: "
                f"{BECAUSE.get(finding.get('state'), 'not established')}"
                f", on the {SIDE.get(finding.get('side'), 'unstated')} read"
            )
        out.append("")

    # -- differences ------------------------------------------------------
    out.append("## Differences established")
    out.append("")
    if not differences:
        out.append("None on the dimensions compared.")
    else:
        out.append("| Item | What differs | Before | After |")
        out.append("| --- | --- | --- | --- |")
        for finding in differences:
            observed = finding.get("observed", {})
            out.append(
                f"| `{finding['item']}` | {IN_ENGLISH[finding['dimension']]} "
                f"| {_plain(observed.get('baseline'))} "
                f"| {_plain(observed.get('verification'))} |"
            )
    out.append("")

    # -- evidence ---------------------------------------------------------
    out.append("## Evidence")
    out.append("")
    out.append(
        "This report is derived. The record it is derived from is delivered "
        "with it, and anyone holding both reads can recompute the record and "
        "check that it says what this says."
    )
    out.append("")
    out.append("| | Read | Taken | Digest of what it observed |")
    out.append("| --- | --- | --- | --- |")
    for label, side in (("Before", baseline), ("After", verification)):
        out.append(
            f"| {label} | {side['read_id']} | {side['taken_at']} "
            f"| `{side['evidence_hash']}` |"
        )
    out.append("")
    out.append(f"Record digest: `{digest(document)}`")
    out.append("")
    move = document["move"]
    out.append(f"Move: {move['kind']}. Produced by {move['produced_by']}.")
    if move.get("performed_by"):
        out.append(f"The move itself was performed by {move['performed_by']}.")
    out.append("")

    # -- limitations ------------------------------------------------------
    out.append("## Limitations")
    out.append("")
    out.append(
        "- A difference is established only where **both** reads could see the "
        "item. Where either could not, the result is recorded as not "
        "established and never as a loss."
    )
    content = next((d for d in compared if d["name"] == "content"), None)
    if content and content.get("method") == WEIGHED_NOT_READ:
        out.append(
            "- **Content was compared by size alone.** Two files of equal size "
            "differ, so nothing in this report says the contents match."
        )
    out.append(
        "- This report describes the two reads it names. It says nothing about "
        "anything outside the estate they declare."
    )
    out.append("")

    # -- appendix ---------------------------------------------------------
    out.append("## Appendix: every finding")
    out.append("")
    if not findings:
        out.append("There are none.")
    else:
        out.append("| Item | Dimension | Outcome | Note |")
        out.append("| --- | --- | --- | --- |")
        for finding in findings:
            note = finding.get("detail") or BECAUSE.get(finding.get("state"), "")
            out.append(
                f"| `{finding['item']}` | {finding['dimension']} "
                f"| {finding['outcome']} | {note} |"
            )
    out.append("")
    if fmt == "html":
        return _html(out, f"Migration verification: {baseline['estate']}")
    if fmt != "markdown":
        raise ValueError(
            f"{fmt!r} is not a format this writes: markdown or html. A report "
            "that guessed would hand somebody a file whose contents are not "
            "what its name promises"
        )
    return "\n".join(out)


def _plain(value: Any) -> str:
    """A value as a reader sees it, without pretending a list is a sentence."""
    if value is None:
        return "not carried"
    if isinstance(value, bool):
        return "present" if value else "absent"
    if isinstance(value, list):
        return ", ".join(_plain(v) for v in value) or "none"
    return str(value)


# ---------------------------------------------------------------------------
# the same report, in a browser
# ---------------------------------------------------------------------------
#
# SELF-CONTAINED, ALWAYS. No stylesheet, no font, no script from anywhere else.
# A report is opened months later, often from an archive, sometimes on a
# machine with no network — and one that renders differently depending on
# whether a CDN answered is a document whose appearance is somebody else's
# decision.

STYLE = """
:root { color-scheme: light dark; }
body { max-width: 46rem; margin: 3rem auto; padding: 0 1.5rem;
       font: 16px/1.6 ui-serif, Georgia, serif; }
h1 { font-size: 1.6rem; line-height: 1.25; }
h2 { font-size: 1.15rem; margin-top: 2.5rem;
     border-top: 1px solid color-mix(in srgb, currentColor 20%, transparent);
     padding-top: 1.2rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0;
        display: block; overflow-x: auto; }
th, td { text-align: left; padding: .45rem .7rem; vertical-align: top;
         border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent); }
th { font-weight: 600; }
code { font: .85em ui-monospace, monospace; word-break: break-all; }
li { margin: .35rem 0; }
"""


def _escape(text: str) -> str:
    for raw, safe in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")):
        text = text.replace(raw, safe)
    return text


def _inline(text: str) -> str:
    """Bold, italic and code, and nothing that could carry markup through.

    Escaping happens first and unconditionally. An estate names its own files,
    and a file named after a script tag is a file, not an instruction.
    """
    text = _escape(text)
    for pattern, tag in (
        (r"\*\*(.+?)\*\*", "strong"),
        (r"`(.+?)`", "code"),
        (r"(?<!\*)\*([^*]+?)\*(?!\*)", "em"),
    ):
        text = re.sub(pattern, rf"<{tag}>\1</{tag}>", text)
    return text


def _html(lines: list[str], title: str) -> str:
    """The Markdown lines, as a page. Same content, same order, same claims."""
    out = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{_escape(title)}</title><style>{STYLE}</style>",
        "</head><body>",
    ]
    table: list[str] = []
    listing = False

    def close_table() -> None:
        if not table:
            return
        head, *body = [row for row in table if not set(row.strip()) <= {"|", "-", " "}]
        cells = lambda row, tag: (  # noqa: E731
            "<tr>"
            + "".join(
                f"<{tag}>{_inline(c.strip())}</{tag}>"
                for c in row.strip("|").split("|")
            )
            + "</tr>"
        )
        out.append(
            "<table>"
            + cells(head, "th")
            + "".join(cells(r, "td") for r in body)
            + "</table>"
        )
        table.clear()

    def close_list() -> None:
        nonlocal listing
        if listing:
            out.append("</ul>")
            listing = False

    for line in lines:
        if line.startswith("|"):
            close_list()
            table.append(line)
            continue
        close_table()

        if line.startswith("- "):
            if not listing:
                out.append("<ul>")
                listing = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        close_list()

        if line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")

    close_table()
    close_list()
    out.append("</body></html>")
    return "\n".join(out) + "\n"
