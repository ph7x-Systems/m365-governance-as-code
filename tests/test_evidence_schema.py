"""The evidence schema, and what a collector may not hand over."""

from __future__ import annotations

import json

import pytest

from m365_governance.validator import validate_evidence_document

from conftest import FIXTURES, evidence, sabotage


def problems(document: dict) -> list:
    return validate_evidence_document(document, "<test>")


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.stem)
def test_every_fixture_matches_the_schema(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    assert problems(document) == []


def test_provenance_is_required():
    broken = sabotage(evidence("site-two-owners"), lambda d: d.pop("provenance"))
    assert problems(broken)


def test_identity_kind_is_required():
    """A delegated run must never be read as a tenant-wide statement."""
    broken = sabotage(
        evidence("site-two-owners"), lambda d: d["provenance"].pop("identity_kind")
    )
    assert problems(broken)


def test_an_observed_fact_must_carry_a_value():
    broken = sabotage(
        evidence("list-within-limit"),
        lambda d: d["facts"]["items"]["count"].pop("value"),
    )
    assert problems(broken)


def test_absence_must_carry_a_reason():
    """null may not carry six meanings."""
    broken = sabotage(
        evidence("list-count-not-collected"),
        lambda d: d["facts"]["items"]["count"].pop("detail"),
    )
    assert problems(broken)


def test_complete_expansion_may_not_also_carry_a_lower_bound():
    broken = sabotage(
        evidence("site-two-owners"),
        lambda d: d["facts"]["owners"].update(minimum_count=1),
    )
    assert problems(broken)


def test_incomplete_expansion_may_not_carry_an_exact_count():
    broken = sabotage(
        evidence("site-partial-expansion-decides"),
        lambda d: d["facts"]["owners"].update(effective_count=3),
    )
    assert problems(broken)


def test_a_collector_may_not_return_a_conclusion():
    """No is_compliant, no risk, no score, no recommended_action."""
    broken = sabotage(
        evidence("site-two-owners"),
        lambda d: d["facts"]["owners"].update(is_compliant=True),
    )
    assert problems(broken)


def test_an_unknown_collection_state_is_rejected():
    broken = sabotage(
        evidence("list-count-not-collected"),
        lambda d: d["facts"]["items"]["count"].update(state="probably-fine"),
    )
    assert problems(broken)
