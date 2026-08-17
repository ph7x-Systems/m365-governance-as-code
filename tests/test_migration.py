"""The migration verification contract, and the rules a schema cannot hold.

The interesting tests here are not about shape. They are about the four ways a
verification record can be well-formed and still say something false: a
baseline taken after the move, one read compared against itself, a finding on a
dimension nobody examined, and content declared to match when it was only
weighed.
"""

from __future__ import annotations

import pytest
from conftest import SCHEMAS

from m365_governance import canonical, migration, registry


@pytest.fixture(scope="module")
def schemas():
    return registry.SchemaRegistry.load(SCHEMAS)


def read(which: str, *, at: str, digest: str, coverage=None) -> dict:
    return {
        "read_id": f"{which}-001",
        "taken_at": at,
        "estate": "contoso-projects",
        "canonical_hash": digest,
        "coverage": coverage or [],
    }


BEFORE = read("baseline", at="2026-03-01T09:00:00Z", digest="a" * 64)
AFTER = read("verification", at="2026-03-08T09:00:00Z", digest="b" * 64)

MOVE = {
    "kind": "tenant-to-tenant",
    "performed_by": "a migration tool",
    "produced_by": "m365-governance 0.1.0",
}


def record(**overrides) -> dict:
    document = {
        "$schema": migration.contract(),
        "baseline": BEFORE,
        "verification": AFTER,
        "move": MOVE,
        "dimensions": [{"name": "presence", "state": "compared"}],
        "findings": [],
    }
    document.update(overrides)
    return document


def test_the_contract_is_read_from_the_schema_and_not_written_down_twice():
    assert migration.contract().endswith("/migration-verification/1.0.0")


def test_a_clean_record_validates_against_the_contract_it_declares(schemas):
    assert schemas.problems(record()) == []
    assert migration.verify(record(), schemas=schemas) == []


def test_the_digest_is_the_canonical_form_a_consumer_reproduces():
    document = record()
    assert migration.digest(document) == canonical.digest(document)


# -- the four ways to be well-formed and wrong ------------------------------


def test_a_baseline_taken_after_the_move_is_refused(schemas):
    """The product's central rule. Both reads exist; the order makes it a lie."""
    inverted = record(
        baseline=read("baseline", at="2026-03-08T09:00:00Z", digest="a" * 64),
        verification=read("verification", at="2026-03-01T09:00:00Z", digest="b" * 64),
    )
    assert schemas.problems(inverted) == [], "shape is fine, which is the point"

    problems = migration.verify(inverted, schemas=schemas)
    assert problems and "not earlier than the move" in problems[0]


def test_a_read_compared_against_itself_is_refused(schemas):
    """It passes everything and establishes nothing."""
    same = "c" * 64
    narcissus = record(
        baseline=read("baseline", at="2026-03-01T09:00:00Z", digest=same),
        verification=read("verification", at="2026-03-08T09:00:00Z", digest=same),
    )
    problems = migration.verify(same := narcissus, schemas=schemas)
    assert problems and "one read against itself" in problems[0]


def test_a_finding_on_an_undeclared_dimension_is_refused(schemas):
    undeclared = record(
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "permissions",
                "outcome": "fail",
                "observed": {"baseline": "unique", "verification": "inherited"},
            }
        ]
    )
    problems = migration.verify(undeclared, schemas=schemas)
    assert problems and "does not declare" in problems[0]


def test_a_finding_on_a_dimension_declared_not_compared_is_refused(schemas):
    contradiction = record(
        dimensions=[
            {"name": "presence", "state": "compared"},
            {
                "name": "versions",
                "state": "not-compared",
                "reason": "version history was out of scope for this project",
            },
        ],
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "versions",
                "outcome": "fail",
                "observed": {"baseline": 12, "verification": 1},
            }
        ],
    )
    problems = migration.verify(contradiction, schemas=schemas)
    assert problems and "was not compared" in problems[0]


def test_content_weighed_by_size_may_never_be_reported_as_matching(schemas):
    """Two files of equal size differ, and the record refuses to forget it."""
    weighed = record(
        dimensions=[{"name": "content", "state": "compared", "method": "size-only"}],
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "content",
                "outcome": "pass",
            }
        ],
    )
    problems = migration.verify(weighed, schemas=schemas)
    assert problems and "compared by size alone" in problems[0]


def test_the_schema_refuses_it_too_when_the_finding_names_its_own_method(schemas):
    weighed = record(
        dimensions=[{"name": "content", "state": "compared", "method": "digest"}],
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "content",
                "outcome": "pass",
                "method": "size-only",
            }
        ],
    )
    assert schemas.problems(weighed) != []


def test_unknown_is_available_where_pass_is_not(schemas):
    """The strongest honest statement, and the reason the contract exists."""
    honest = record(
        dimensions=[{"name": "content", "state": "compared", "method": "size-only"}],
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "content",
                "outcome": "unknown",
                "side": "both",
                "state": "partial",
                "detail": "compared by size; content was not hashed on either side",
            }
        ],
    )
    assert schemas.problems(honest) == []
    assert migration.verify(honest, schemas=schemas) == []


# -- what the schema itself holds -------------------------------------------


def test_a_dimension_not_compared_must_say_why(schemas):
    silent = record(dimensions=[{"name": "versions", "state": "not-compared"}])
    assert schemas.problems(silent) != []


def test_content_compared_must_say_how(schemas):
    vague = record(dimensions=[{"name": "content", "state": "compared"}])
    assert schemas.problems(vague) != []


def test_a_failure_must_say_what_differed(schemas):
    accusation = record(
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "presence",
                "outcome": "fail",
            }
        ]
    )
    assert schemas.problems(accusation) != []


def test_an_unknown_must_say_which_side_and_why(schemas):
    vague = record(
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "presence",
                "outcome": "unknown",
            }
        ]
    )
    assert schemas.problems(vague) != []


def test_a_pass_may_not_carry_an_absence_reason(schemas):
    """`unknown` fields on a passing finding would be a contradiction in shape."""
    confused = record(
        findings=[
            {
                "item": "/Shared Documents/plan.xlsx",
                "dimension": "presence",
                "outcome": "pass",
                "side": "both",
                "state": "partial",
            }
        ]
    )
    assert schemas.problems(confused) != []


def test_coverage_states_come_from_the_evidence_contract(schemas):
    """One owner for the vocabulary, referenced rather than copied."""
    covered = record(
        baseline=read(
            "baseline",
            at="2026-03-01T09:00:00Z",
            digest="a" * 64,
            coverage=[
                {
                    "scope": "/Shared Documents/Archive",
                    "state": "permission-denied",
                    "detail": "the reading identity had no access",
                }
            ],
        )
    )
    assert schemas.problems(covered) == []

    invented = record(
        baseline=read(
            "baseline",
            at="2026-03-01T09:00:00Z",
            digest="a" * 64,
            coverage=[{"scope": "/x", "state": "probably-fine"}],
        )
    )
    assert schemas.problems(invented) != []


def test_there_is_nothing_to_aggregate(schemas):
    """No score, no percentage, no grade — not omitted, unrepresentable."""
    scored = record()
    scored["score"] = 96
    assert schemas.problems(scored) != []


def test_build_refuses_an_incoherent_record_rather_than_producing_it():
    with pytest.raises(migration.Unverifiable, match="not earlier than the move"):
        migration.build(
            baseline=read("baseline", at="2026-03-08T09:00:00Z", digest="a" * 64),
            verification=read(
                "verification", at="2026-03-01T09:00:00Z", digest="b" * 64
            ),
            move=MOVE,
            dimensions=[{"name": "presence", "state": "compared"}],
            findings=[],
        )


def test_build_produces_a_document_that_declares_its_contract():
    document = migration.build(
        baseline=BEFORE,
        verification=AFTER,
        move=MOVE,
        dimensions=[{"name": "presence", "state": "compared"}],
        findings=[],
    )
    assert document["$schema"] == migration.contract()
