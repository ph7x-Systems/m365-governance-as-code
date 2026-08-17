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


# ---------------------------------------------------------------------------
# the comparison
# ---------------------------------------------------------------------------


def side(items: dict, coverage=None) -> dict:
    return {"items": items, "coverage": coverage or []}


PLAN = "/Shared Documents/plan.xlsx"
ARCHIVE = "/Shared Documents/Archive/2019.xlsx"


def test_an_item_that_did_not_arrive_is_a_failure():
    findings = migration.compare(
        baseline=side({PLAN: {}}),
        verification=side({}),
        dimensions=[{"name": "presence", "state": "compared"}],
    )
    assert findings == [
        {
            "item": PLAN,
            "dimension": "presence",
            "outcome": "fail",
            "observed": {"baseline": True, "verification": False},
        }
    ]


def test_an_item_nobody_could_look_for_is_not_a_failure():
    """The rule the whole product turns on.

    The item is absent from the target and the target read says it could not
    see that container. Reporting it missing would be more useful-sounding and
    would be a claim nobody established.
    """
    findings = migration.compare(
        baseline=side({ARCHIVE: {}}),
        verification=side(
            {},
            coverage=[
                {
                    "scope": "/Shared Documents/Archive",
                    "state": "permission-denied",
                    "detail": "the reading identity had no access",
                }
            ],
        ),
        dimensions=[{"name": "presence", "state": "compared"}],
    )
    assert findings == [
        {
            "item": ARCHIVE,
            "dimension": "presence",
            "outcome": "unknown",
            "side": "verification",
            "state": "permission-denied",
            "detail": "the reading identity had no access",
        }
    ]


def test_a_gap_on_a_container_covers_what_is_inside_it():
    """Gaps are declared over containers because that is how reading fails."""
    findings = migration.compare(
        baseline=side({ARCHIVE: {}, PLAN: {}}),
        verification=side(
            {},
            coverage=[{"scope": "/Shared Documents/Archive", "state": "missing"}],
        ),
        dimensions=[{"name": "presence", "state": "compared"}],
    )
    outcomes = {f["item"]: f["outcome"] for f in findings}
    assert outcomes == {ARCHIVE: "unknown", PLAN: "fail"}


def test_a_gap_on_both_sides_is_weaker_than_a_gap_on_one():
    findings = migration.compare(
        baseline=side(
            {ARCHIVE: {}},
            coverage=[{"scope": "/Shared Documents/Archive", "state": "partial"}],
        ),
        verification=side(
            {},
            coverage=[
                {"scope": "/Shared Documents/Archive", "state": "permission-denied"}
            ],
        ),
        dimensions=[{"name": "presence", "state": "compared"}],
    )
    assert findings[0]["side"] == "both"


def test_authorship_rewritten_by_the_move_is_reported_with_both_values():
    """The most common silent loss in a migration, and the least reported."""
    findings = migration.compare(
        baseline=side({PLAN: {"author": "j.mendes@contoso.com"}}),
        verification=side({PLAN: {"author": "svc-migration@contoso.com"}}),
        dimensions=[{"name": "authorship", "state": "compared"}],
    )
    assert findings[0]["outcome"] == "fail"
    assert findings[0]["observed"] == {
        "baseline": "j.mendes@contoso.com",
        "verification": "svc-migration@contoso.com",
    }


def test_content_equal_by_digest_says_nothing_because_nothing_is_wrong():
    findings = migration.compare(
        baseline=side({PLAN: {"content_digest": "d" * 64}}),
        verification=side({PLAN: {"content_digest": "d" * 64}}),
        dimensions=[
            {"name": "content", "state": "compared", "method": "digest"}
        ],
    )
    assert findings == []


def test_content_equal_by_size_alone_is_unknown_and_never_silent():
    """Equal by the only measure taken, and the measure cannot carry the claim."""
    findings = migration.compare(
        baseline=side({PLAN: {"content_digest": None, "size": 4096}}),
        verification=side({PLAN: {"content_digest": None, "size": 4096}}),
        dimensions=[
            {"name": "size", "state": "compared"},
            {"name": "content", "state": "compared", "method": "size-only"},
        ],
    )
    content = [f for f in findings if f["dimension"] == "content"]
    assert content and content[0]["outcome"] == "unknown"
    assert "not hashed" in content[0]["detail"]


def test_an_attribute_the_read_never_carried_is_unknown_not_a_pass():
    """A thinner read than the record claims, said out loud."""
    findings = migration.compare(
        baseline=side({PLAN: {"versions": 12}}),
        verification=side({PLAN: {}}),
        dimensions=[{"name": "versions", "state": "compared"}],
    )
    assert findings[0]["outcome"] == "unknown"
    assert findings[0]["state"] == "partial"


def test_a_dimension_declared_not_compared_produces_nothing():
    findings = migration.compare(
        baseline=side({PLAN: {"versions": 12}}),
        verification=side({PLAN: {"versions": 1}}),
        dimensions=[
            {
                "name": "versions",
                "state": "not-compared",
                "reason": "out of scope for this project",
            }
        ],
    )
    assert findings == []


def test_counts_that_differ_are_reported_against_the_estate():
    findings = migration.compare(
        baseline=side({PLAN: {}, ARCHIVE: {}}),
        verification=side({PLAN: {}}),
        dimensions=[{"name": "count", "state": "compared"}],
    )
    assert findings == [
        {
            "item": "<estate>",
            "dimension": "count",
            "outcome": "fail",
            "observed": {"baseline": 2, "verification": 1},
        }
    ]


def test_the_comparison_is_reproducible(schemas):
    """Same two reads, same findings, same order, same digest."""
    args = dict(
        baseline=side({ARCHIVE: {"author": "a"}, PLAN: {"author": "b"}}),
        verification=side({PLAN: {"author": "svc"}}),
        dimensions=[
            {"name": "presence", "state": "compared"},
            {"name": "authorship", "state": "compared"},
        ],
    )
    first = migration.compare(**args)
    second = migration.compare(**args)
    assert first == second
    assert canonical.digest(first) == canonical.digest(second)


def test_a_produced_record_verifies_end_to_end(schemas):
    """Compare, build, validate — the whole of step three of the build order."""
    dimensions = [
        {"name": "presence", "state": "compared"},
        {"name": "authorship", "state": "compared"},
        {
            "name": "content",
            "state": "compared",
            "method": "size-only",
        },
    ]
    findings = migration.compare(
        baseline=side(
            {
                PLAN: {"author": "j.mendes@contoso.com", "content_digest": None},
                ARCHIVE: {"author": "r.silva@contoso.com", "content_digest": None},
            }
        ),
        verification=side(
            {PLAN: {"author": "svc-migration@contoso.com", "content_digest": None}},
            coverage=[
                {"scope": "/Shared Documents/Archive", "state": "permission-denied"}
            ],
        ),
        dimensions=dimensions,
    )
    document = migration.build(
        baseline=BEFORE,
        verification=AFTER,
        move=MOVE,
        dimensions=dimensions,
        findings=findings,
    )
    assert schemas.problems(document) == []
    assert migration.verify(document, schemas=schemas) == []

    outcomes = {(f["item"], f["dimension"]): f["outcome"] for f in findings}
    assert outcomes[(ARCHIVE, "presence")] == "unknown"
    assert outcomes[(PLAN, "authorship")] == "fail"


# ---------------------------------------------------------------------------
# reads in, records out
# ---------------------------------------------------------------------------

FIXTURES = SCHEMAS.parent / "fixtures" / "migration"


def fixture(name: str) -> dict:
    import json

    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_the_published_reads_validate_against_the_read_contract(schemas):
    for name in ("before-cutover", "after-cutover"):
        assert schemas.problems(fixture(name)) == [], name


def test_a_read_is_named_by_digest_and_never_copied():
    document = fixture("before-cutover")
    side = migration.reference(document)
    assert side["canonical_hash"] == canonical.digest(document)
    assert "items" not in side


def test_the_method_is_derived_from_the_reads_not_asserted():
    """A caller cannot claim a comparison the evidence does not support."""
    before, after = fixture("before-cutover"), fixture("after-cutover")
    content = next(
        d for d in migration.dimensions_for(before, after) if d["name"] == "content"
    )
    assert content == {
        "name": "content",
        "state": "compared",
        "method": "size-only",
    }, "the reads carry sizes and null digests, so size-only is the only honest method"


def test_digests_present_produce_a_digest_comparison():
    before, after = fixture("before-cutover"), fixture("after-cutover")
    for document in (before, after):
        for item in document["items"].values():
            item["content_digest"] = "e" * 64
    content = next(
        d for d in migration.dimensions_for(before, after) if d["name"] == "content"
    )
    assert content["method"] == "digest"


def test_permissions_in_a_different_order_are_not_a_change():
    """The same two grants, reordered by the move. Noise, and expensive noise."""
    findings = migration.compare(
        baseline=side({PLAN: {"permissions": [["Owners", "full"], ["Members", "edit"]]}}),
        verification=side(
            {PLAN: {"permissions": [["Members", "edit"], ["Owners", "full"]]}}
        ),
        dimensions=[{"name": "permissions", "state": "compared"}],
    )
    assert findings == []


def test_a_count_is_unknown_when_part_of_the_estate_could_not_be_read():
    """A count is a claim about the whole container, so one gap invalidates it."""
    findings = migration.compare(
        baseline=side({PLAN: {}, ARCHIVE: {}}),
        verification=side(
            {PLAN: {}},
            coverage=[
                {"scope": "/Shared Documents/Archive", "state": "permission-denied"}
            ],
        ),
        dimensions=[{"name": "count", "state": "compared"}],
    )
    assert findings[0]["outcome"] == "unknown"
    assert "whole estate" in findings[0]["detail"]


def test_the_fixture_pair_produces_a_record_that_verifies(schemas):
    """The whole product, from the two documents a customer would send."""
    document = migration.record(
        baseline=fixture("before-cutover"),
        verification=fixture("after-cutover"),
        move={"kind": "tenant-to-tenant", "produced_by": "m365-governance test"},
    )
    assert schemas.problems(document) == []
    assert migration.verify(document, schemas=schemas) == []

    outcomes = {(f["item"].split("/")[-1], f["dimension"]): f["outcome"]
                for f in document["findings"]}

    # The archive could not be read after the move. It is not reported missing.
    assert outcomes[("Minutes 2019.docx", "presence")] == "unknown"
    # Authorship was rewritten to the migration account, which is a real loss.
    assert outcomes[("Handover.docx", "authorship")] == "fail"
    # Thirty-one versions arrived; seven became one.
    assert outcomes[("Handover.docx", "versions")] == "fail"
    # Permissions were reordered and are not reported at all.
    assert ("Handover.docx", "permissions") not in outcomes
    # Nothing anywhere claims content matched.
    assert all(
        f["outcome"] != "pass" for f in document["findings"] if f["dimension"] == "content"
    )
