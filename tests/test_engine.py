"""The engine: six states, bounded evaluation, and a fixed resolution order."""

from __future__ import annotations

import pytest

from conftest import evidence, sabotage
from m365_governance.engine import evaluate_rule, resolve
from m365_governance.results import Outcome

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


# ---------------------------------------------------------------------------
# Unique permission scopes: a documented limit and a documented recommendation
# reading the same number
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,hard_limit,recommended",
    [
        ("list-scopes-within-recommended", Outcome.PASS, Outcome.PASS),
        ("list-scopes-over-recommended", Outcome.PASS, Outcome.FAIL),
        ("list-scopes-over-hard-limit", Outcome.FAIL, Outcome.FAIL),
        ("list-scopes-not-counted", Outcome.UNKNOWN, Outcome.UNKNOWN),
        # The bound proves one and not the other, which is the whole point.
        ("list-scopes-counted-in-part", Outcome.UNKNOWN, Outcome.FAIL),
    ],
)
def test_scope_rules_on_the_same_number(fixture, hard_limit, recommended):
    from conftest import rule

    assert evaluate_rule(rule("SPO-LIST-002"), evidence(fixture)).outcome is hard_limit
    assert evaluate_rule(rule("SPO-LIST-003"), evidence(fixture)).outcome is recommended


def test_a_partial_count_is_a_lower_bound_not_an_absence():
    """Evidence is monotonic: a collector that stopped at 20,000 items saw at
    least what it counted. Treating that as absent throws away an answer."""
    from conftest import rule

    result = evaluate_rule(
        rule("SPO-LIST-003"), evidence("list-scopes-counted-in-part")
    )
    assert result.outcome is Outcome.FAIL
    used = {e.path: e for e in result.evidence_used}["permissions.unique_scope_count"]
    assert used.lower_bound == 6100
    assert used.exact is None


def test_a_partial_count_cannot_prove_the_higher_threshold():
    from conftest import rule

    result = evaluate_rule(
        rule("SPO-LIST-002"), evidence("list-scopes-counted-in-part")
    )
    assert result.outcome is Outcome.UNKNOWN


def test_not_counted_is_never_a_pass():
    """The collector did not look. A zero here would be an invention."""
    from conftest import rule

    for rule_id in ("SPO-LIST-002", "SPO-LIST-003"):
        result = evaluate_rule(rule(rule_id), evidence("list-scopes-not-counted"))
        assert result.outcome is Outcome.UNKNOWN
        assert not result.outcome.is_answer


def test_the_two_scope_rules_keep_different_bases():
    """Same number, different kind of claim. Collapsing them would put a
    performance recommendation under the same heading as a hard ceiling."""
    from conftest import rule

    assert rule("SPO-LIST-002")["basis"]["type"] == "documented-limit"
    assert rule("SPO-LIST-003")["basis"]["type"] == "documented-guidance"
    assert rule("SPO-LIST-002")["condition"]["value"] == 50000
    assert rule("SPO-LIST-003")["condition"]["value"] == 5000


# ---------------------------------------------------------------------------
# Sharing: a site that sets no default of its own
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("site-sharing-anyone-default-anyone", Outcome.FAIL),
        ("site-sharing-anyone-default-direct", Outcome.PASS),
        # `None` means the site follows the tenant, and the tenant setting is
        # not in this document. Reading it as "not Anyone" would be a pass
        # built on nothing.
        ("site-sharing-inherits-tenant-default", Outcome.UNKNOWN),
        ("site-sharing-guests-only", Outcome.NOT_APPLICABLE),
        ("site-sharing-not-collected", Outcome.UNKNOWN),
    ],
)
def test_default_link_rule_on_real_enum_values(fixture, expected):
    from conftest import rule

    assert evaluate_rule(rule("SPO-SHARE-002"), evidence(fixture)).outcome is expected


def test_inheriting_the_tenant_default_is_never_a_pass():
    """Found by running the collector against a tenant: every site there
    reported `None`, which the rule would have read as a safe value."""
    from conftest import rule

    result = evaluate_rule(
        rule("SPO-SHARE-002"), evidence("site-sharing-inherits-tenant-default")
    )
    assert result.outcome is Outcome.UNKNOWN
    assert not result.outcome.is_answer


def test_the_declared_setting_is_kept_beside_the_effective_one():
    """Both are in the evidence. The rule reads the effective value; a reader
    needs the declared one to understand why it is missing."""
    facts = evidence("site-sharing-inherits-tenant-default")["facts"]["sharing"]
    assert facts["default_link_type"]["value"] == "None"
    assert facts["effective_default_link_type"]["state"] == "missing"
    assert "follows the tenant" in facts["effective_default_link_type"]["detail"]


@pytest.mark.parametrize(
    "value",
    [
        "Disabled",
        "ExternalUserSharingOnly",
        "ExternalUserAndGuestSharing",
        "ExistingExternalUserSharingOnly",
    ],
)
def test_the_capability_rule_uses_values_the_product_returns(value):
    """Read out of the loaded PnP assemblies and confirmed against a tenant.
    A rule comparing against "Anyone" would have matched nothing."""
    from conftest import rule

    assert rule("SPO-SHARE-001")["condition"]["value"] in {
        "Disabled",
        "ExternalUserSharingOnly",
        "ExternalUserAndGuestSharing",
        "ExistingExternalUserSharingOnly",
    }
    assert value  # the four the enum defines
