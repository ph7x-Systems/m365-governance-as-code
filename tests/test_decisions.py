"""The three semantic decisions, held in place by tests.

Each of these was a choice the documents did not fix. They are decided now,
and a test exists for each so the decision cannot be reversed by accident:
none of the three would fail any other check if it silently changed.
"""

from __future__ import annotations

import copy
import json

from conftest import evidence, rule, sabotage
from m365_governance.engine import evaluate, evaluate_rule
from m365_governance.reporting import to_markdown
from m365_governance.results import Outcome
from m365_governance.validator import validate_structure

# ---------------------------------------------------------------------------
# 1. A true condition is a failure
# ---------------------------------------------------------------------------


def test_a_true_condition_is_a_failure(site_rule):
    """`owners.count less-than 2` against one owner is true, and reports fail."""
    result = evaluate_rule(site_rule, evidence("site-one-owner"))
    assert result.outcome is Outcome.FAIL


def test_a_false_condition_is_a_pass(site_rule):
    result = evaluate_rule(site_rule, evidence("site-two-owners"))
    assert result.outcome is Outcome.PASS


def test_inverting_the_operator_inverts_the_result(site_rule):
    """The direction is not inferable from the file, so it is pinned here.

    Nothing else in the suite fails if the engine flips: the schema, the rule
    graph and every message still validate. Only this assertion notices.
    """
    inverted = sabotage(
        site_rule, lambda r: r["condition"].update(operator="greater-than-or-equal")
    )
    assert evaluate_rule(inverted, evidence("site-two-owners")).outcome is Outcome.FAIL
    assert evaluate_rule(inverted, evidence("site-one-owner")).outcome is Outcome.PASS


def test_a_documented_limit_states_the_limit_next_to_the_observed_value():
    """The reader sees both numbers without following the link."""
    data = rule("SPO-LIST-001")
    assert data["basis"]["type"] == "documented-limit"
    limit = data["basis"]["limit"]["value"]
    fail_message = data["outcomes"]["fail"]["message"]
    assert f"{limit:,}" in fail_message, (
        f"the fail message must state the limit ({limit:,}) beside the observed value"
    )
    assert "{" + data["condition"]["evidence"] + "}" in fail_message


# ---------------------------------------------------------------------------
# 2. The engine may derive a documented fact, and never invent one
# ---------------------------------------------------------------------------


def test_a_derived_count_carries_its_bound_and_its_state(site_rule):
    result = evaluate_rule(site_rule, evidence("site-partial-expansion-decides"))
    used = {e.path: e for e in result.evidence_used}["owners.count"]
    assert used.exact is None
    assert used.lower_bound == 3
    assert used.state == "partial"
    assert used.detail and "lower bound" in used.detail


def test_a_bound_is_printed_as_a_bound_and_never_as_a_value(site_rule):
    """`at least 3` may never render as `3`."""
    result = evaluate_rule(site_rule, evidence("site-partial-expansion-decides"))
    assert "at least 3" in result.message
    assert "has 3 owners" not in result.message


def test_the_derivation_appears_in_both_report_formats():
    run = evaluate([rule("SPO-SITE-001")], evidence("site-partial-expansion-decides"))
    markdown = to_markdown(run)
    assert "at least 3" in markdown

    payload = json.loads(json.dumps(run.to_dict()))
    used = payload["results"][0]["evidence_used"][0]
    assert used["value"] is None
    assert used["lower_bound"] == 3
    assert used["state"] == "partial"


def test_the_engine_does_not_invent_a_count_when_the_bound_is_absent(site_rule):
    """No expansion fields at all is unknown, not zero."""
    broken = sabotage(
        evidence("site-partial-expansion-decides"),
        lambda d: d["facts"]["owners"].pop("minimum_count"),
    )
    assert evaluate_rule(site_rule, broken).outcome is Outcome.UNKNOWN


# ---------------------------------------------------------------------------
# 3. No composition in the grammar
# ---------------------------------------------------------------------------


def _schema_problems(document: dict) -> list:
    return validate_structure(document, "rule.schema.json", "<test>")


def test_a_composed_condition_is_rejected(site_rule):
    broken = copy.deepcopy(site_rule)
    broken["condition"] = {
        "all_of": [
            {"operator": "less-than", "evidence": "owners.count", "value": 2},
            {"operator": "equals", "evidence": "owners.count", "value": 0},
        ]
    }
    assert _schema_problems(broken)


def test_a_condition_with_two_evidence_paths_is_rejected(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["condition"].update(evidence_2="owners.total")
    )
    assert _schema_problems(broken)


def test_two_facts_are_expressed_as_applicability_plus_condition():
    """The shape that replaces a conjunction, and why it is better.

    A conjunction would report `pass` for a list that already has unique
    permissions. Applicability reports `not-applicable`, which is a different
    line in the report and a truthful one: the rule had nothing to say.
    """
    list_rule = rule("SPO-LIST-001")
    assert list_rule["applicability"]["evidence"] == "permissions.inheritance_broken"
    assert list_rule["condition"]["evidence"] == "items.count"

    result = evaluate_rule(list_rule, evidence("list-unique-permissions"))
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert not result.outcome.is_answer
