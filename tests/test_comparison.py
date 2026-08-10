"""A comparison relates two assessments and belongs to neither.

Every test here is about a boundary rather than about arithmetic: what a
comparison names, what it refuses to carry, and the one question it will not
answer however obvious the answer looks.
"""

from __future__ import annotations

import json

import pytest

from conftest import DATA
from m365_governance import assessment, comparison
from m365_governance.engine import evaluate
from m365_governance.loader import load_rules
from m365_governance.registry import SchemaRegistry
from m365_governance.results import RunSet

FIXTURES = DATA / "fixtures" / "sharepoint"
SAMPLE = DATA / "fixtures" / "comparison" / "sharing-mitigated.json"


def rules() -> list[dict]:
    return [loaded.data for loaded in load_rules(DATA / "rules")]


def built(name: str, when: str, **edit) -> dict:
    document = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    for path, value in edit.items():
        block, key = path.split("__")
        document["provenance"][block][key] = value
    return assessment.build(
        RunSet([evaluate(rules(), document)]),
        [document],
        engine_version="1.0.0b1",
        created_at=when,
    )


def pair() -> tuple[dict, dict]:
    """The same tenant before and after somebody turned Anyone links off."""
    return (
        built("tenant-sharing-default-anyone-and-edit", "2026-07-01T09:00:00Z"),
        built("tenant-sharing-mitigated", "2026-08-01T09:00:00Z"),
    )


def contracts() -> SchemaRegistry:
    return SchemaRegistry.load(DATA / "schemas")


def compared() -> dict:
    before, after = pair()
    return comparison.build(before, after, engine_version="1.0.0b1")


def test_the_committed_sample_matches_its_contract():
    problems = contracts().problems(json.loads(SAMPLE.read_text(encoding="utf-8")))
    assert not problems, problems[0]


def test_what_the_engine_builds_matches_its_contract():
    problems = contracts().problems(compared())
    assert not problems, problems[0]


def test_each_side_is_named_and_neither_is_embedded():
    """A comparison that carried both assessments would duplicate the canonical
    truth it describes, and the copy is what somebody edits."""
    document = compared()
    for side in ("before", "after"):
        assert len(document[side]["canonical_hash"]) == 64
        assert document[side]["assessment_id"]
        assert "canonical" not in document[side]
    assert "runs" not in json.dumps(document["before"])


def test_a_side_is_named_by_identity_and_never_by_path():
    """A path says where a file sat on one machine, not what it held."""
    text = json.dumps(compared())
    assert "/" not in json.dumps(compared()["before"])
    assert ".json" not in text


def test_the_engine_that_produced_it_is_recorded():
    """A diff nobody can reproduce is an opinion about history."""
    assert compared()["diff"]["produced_by"] == "1.0.0b1"


def test_it_is_derived_and_reproducible():
    """Given the same two assessments it produces the same bytes. Nothing is
    read from the clock and nothing from the installation."""
    assert json.dumps(compared(), sort_keys=True) == json.dumps(
        compared(), sort_keys=True
    )


def test_the_same_assessment_twice_is_an_empty_answer():
    before, _ = pair()
    document = comparison.build(before, before, engine_version="1.0.0b1")
    assert document["diff"]["changes"] == []
    assert contracts().problems(document) == []


# ---------------------------------------------------------------------------
# observation and attribution are two fields, and one of them stays empty
# ---------------------------------------------------------------------------


def test_what_was_observed_is_recorded_and_why_is_not():
    document = compared()
    changes = document["diff"]["changes"]
    assert changes, "two different assessments produced nothing"

    for change in changes:
        assert set(change["changes"]) <= {"evidence", "outcome", "rule-version"}
        # Nothing here evaluates causality, so nothing here may claim it.
        assert change["attribution"]["state"] != "established"


def test_two_candidates_are_ambiguous_and_never_a_cause():
    """Evidence and a rule version moving together is exactly the case where
    saying which one mattered needs a counterfactual nobody ran."""
    assert comparison._attribution(["evidence", "outcome", "rule-version"]) == {
        "state": "ambiguous",
        "factors": ["evidence", "rule-version"],
    }


def test_one_candidate_is_still_not_a_cause():
    """The outcome moved and so did one other thing. Saying the second produced
    the first is the same counterfactual, with fewer suspects."""
    assert comparison._attribution(["evidence", "outcome"]) == {
        "state": "not-evaluated"
    }


def test_the_outcome_is_never_among_its_own_causes():
    for moved in (["outcome"], ["evidence", "outcome"], ["outcome", "rule-version"]):
        attribution = comparison._attribution(moved)
        assert "outcome" not in attribution.get("factors", [])


# ---------------------------------------------------------------------------
# what it refuses
# ---------------------------------------------------------------------------


def test_two_tenants_are_not_one_comparison():
    """Across two estates every count in it would be a sum over organisations
    nobody manages together."""
    before, _ = pair()
    elsewhere = built(
        "tenant-sharing-mitigated",
        "2026-08-01T09:00:00Z",
        tenant__host="fabrikam.sharepoint.com",
    )
    with pytest.raises(comparison.Incomparable, match="different tenants"):
        comparison.build(before, elsewhere, engine_version="1.0.0b1")


@pytest.mark.parametrize("side", ["before", "after"])
def test_an_assessment_that_does_not_verify_is_refused(side):
    """Comparing a document that moved is comparing something nobody can name.
    The digests exist for this, and a comparison is where they are cheapest to
    check and most expensive to skip."""
    sides = dict(zip(("before", "after"), pair(), strict=True))
    sides[side]["canonical"]["versions"]["engine"] = "forged"

    with pytest.raises(comparison.Incomparable, match="does not verify"):
        comparison.build(sides["before"], sides["after"], engine_version="1.0.0b1")
