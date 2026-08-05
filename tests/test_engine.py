"""The engine: six states, bounded evaluation, and a fixed resolution order."""

from __future__ import annotations

import pytest

from m365_governance.engine import evaluate_rule, resolve
from m365_governance.results import Outcome

from conftest import evidence, sabotage


# ---------------------------------------------------------------------------
# SPO-SITE-001, a convention over a counted collection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("site-two-owners", Outcome.PASS),
        ("site-one-owner", Outcome.FAIL),
        ("site-owners-not-collected", Outcome.UNKNOWN),
        ("site-partial-expansion-decides", Outcome.PASS),
        ("site-partial-expansion-undecided", Outcome.UNKNOWN),
    ],
)
def test_site_rule_outcomes(site_rule, fixture, expected):
    assert evaluate_rule(site_rule, evidence(fixture)).outcome is expected


def test_permission_denied_is_not_a_pass(site_rule):
    result = evaluate_rule(site_rule, evidence("site-owners-not-collected"))
    assert result.outcome is Outcome.UNKNOWN
    assert not result.outcome.is_answer


def test_incomplete_expansion_still_decides_when_the_bound_settles_it(site_rule):
    """Three direct owners and one unexpanded group prove `at least 3`."""
    result = evaluate_rule(site_rule, evidence("site-partial-expansion-decides"))
    assert result.outcome is Outcome.PASS
    assert "at least 3" in result.message
    used = {e.path: e for e in result.evidence_used}
    assert used["owners.count"].lower_bound == 3
    assert used["owners.count"].exact is None


def test_a_lower_bound_can_prove_pass_and_never_fail(site_rule):
    """`minimum_count: 1` does not settle `owners < 2`: the group may hold one."""
    result = evaluate_rule(site_rule, evidence("site-partial-expansion-undecided"))
    assert result.outcome is Outcome.UNKNOWN


def test_invalid_evidence_for_the_site_rule(site_rule):
    broken = sabotage(
        evidence("site-two-owners"),
        lambda d: d["facts"].update(
            owners={"state": "invalid", "detail": "effective_count was 'several'"}
        ),
    )
    assert evaluate_rule(site_rule, broken).outcome is Outcome.INVALID_EVIDENCE


# ---------------------------------------------------------------------------
# SPO-LIST-001, a documented limit with an applicability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("list-within-limit", Outcome.PASS),
        ("list-over-limit", Outcome.FAIL),
        ("list-unique-permissions", Outcome.NOT_APPLICABLE),
        ("list-count-invalid", Outcome.INVALID_EVIDENCE),
        ("list-count-not-collected", Outcome.UNKNOWN),
        ("list-inheritance-not-collected", Outcome.UNKNOWN),
    ],
)
def test_list_rule_outcomes(list_rule, fixture, expected):
    assert evaluate_rule(list_rule, evidence(fixture)).outcome is expected


def test_not_applicable_is_not_a_pass(list_rule):
    result = evaluate_rule(list_rule, evidence("list-unique-permissions"))
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert not result.outcome.is_answer


def test_unknown_applicability_does_not_become_not_applicable(list_rule):
    """Whether the rule speaks about this list is itself undecided."""
    result = evaluate_rule(list_rule, evidence("list-inheritance-not-collected"))
    assert result.outcome is Outcome.UNKNOWN


def test_the_fail_message_only_claims_what_the_rule_established(list_rule):
    """The v2.0 correction: applicability proves the inheritance clause."""
    result = evaluate_rule(list_rule, evidence("list-over-limit"))
    assert result.outcome is Outcome.FAIL
    assert "still inherits its permissions" in result.message
    used = {e.path: e for e in result.evidence_used}
    assert used["permissions.inheritance_broken"].exact is False


# ---------------------------------------------------------------------------
# Resolution order
# ---------------------------------------------------------------------------


def test_invalid_evidence_wins_over_not_applicable(list_rule):
    """A malformed value may not vanish beneath an applicability decision."""
    broken = sabotage(
        evidence("list-unique-permissions"),
        lambda d: d["facts"]["items"].update(
            count={"state": "invalid", "detail": "Expected integer"}
        ),
    )
    assert evaluate_rule(list_rule, broken).outcome is Outcome.INVALID_EVIDENCE


def test_not_applicable_wins_over_unknown(list_rule):
    """A rule that does not speak about this resource never says `unknown`."""
    broken = sabotage(
        evidence("list-unique-permissions"),
        lambda d: d["facts"]["items"].update(
            count={"state": "missing", "detail": "not returned"}
        ),
    )
    assert evaluate_rule(list_rule, broken).outcome is Outcome.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# error: the engine describing itself, never the resource
# ---------------------------------------------------------------------------


def test_engine_failure_produces_error_and_not_a_finding(list_rule):
    broken = sabotage(list_rule, lambda r: r.pop("outcomes"))
    result = evaluate_rule(broken, evidence("list-over-limit"))
    assert result.outcome is Outcome.ERROR
    assert not result.outcome.is_answer
    assert result.engine_detail
    assert "not the resource" in result.message


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_a_path_absent_from_the_facts_is_missing_not_zero():
    resolved = resolve({}, "items.count")
    assert resolved.kind == "absent"
    assert resolved.value is None


def test_an_empty_list_is_observed_and_not_absence():
    """`[]` means observed, and there are none."""
    facts = {"sharing": {"links": {"state": "observed", "value": []}}}
    resolved = resolve(facts, "sharing.links")
    assert resolved.kind == "exact"
    assert resolved.value == []
