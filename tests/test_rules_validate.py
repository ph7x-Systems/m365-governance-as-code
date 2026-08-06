"""The rules in the repository validate, and every invariant goes red when broken.

Each test in the sabotage section takes a rule that passes, breaks exactly one
thing, and asserts the specific problem code. A guard nobody has seen fail is
a guard nobody has tested.
"""

from __future__ import annotations

import pytest

from conftest import RULES, rule, sabotage
from m365_governance.loader import LoadedRule
from m365_governance.validator import (
    validate_repository,
    validate_semantics,
    validate_structure,
)


def codes(problems) -> set[str]:
    return {p.code for p in problems}


def check(document: dict) -> list:
    """Both layers, the way the CLI runs them."""
    structural = validate_structure(document, "rule.schema.json", "<test>")
    if structural:
        return structural
    return validate_semantics(document, "<test>")


# ---------------------------------------------------------------------------
# The repository as it stands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule_id", ["SPO-LIST-001", "SPO-SITE-001"])
def test_authored_rules_pass_every_layer(rule_id):
    assert check(rule(rule_id)) == []


def test_every_rule_file_is_covered_by_a_test():
    """A rule added without a test would otherwise pass silently."""
    on_disk = {p.stem for p in RULES.rglob("*.yaml")}
    assert on_disk == {"SPO-LIST-001", "SPO-SITE-001"}, (
        "a rule was added or renamed. Add its cases to tests/test_engine.py "
        "and list it here."
    )


# ---------------------------------------------------------------------------
# Layer 2: structure
# ---------------------------------------------------------------------------


def test_missing_basis_is_rejected(site_rule):
    broken = sabotage(site_rule, lambda r: r.pop("basis"))
    assert "schema" in codes(check(broken))


def test_documented_type_without_source_is_rejected(list_rule):
    broken = sabotage(list_rule, lambda r: r["basis"].update(sources=[]))
    assert "schema" in codes(check(broken))


def test_convention_without_rationale_is_rejected(site_rule):
    broken = sabotage(site_rule, lambda r: r["basis"].pop("rationale"))
    assert "schema" in codes(check(broken))


def test_documented_limit_without_limit_block_is_rejected(list_rule):
    broken = sabotage(list_rule, lambda r: r["basis"].pop("limit"))
    assert "schema" in codes(check(broken))


def test_source_without_checked_at_is_rejected(list_rule):
    broken = sabotage(list_rule, lambda r: r["basis"]["sources"][0].pop("checked_at"))
    assert "schema" in codes(check(broken))


def test_missing_passes_without_resolving_is_rejected(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["limitations"].pop("passes_without_resolving")
    )
    assert "schema" in codes(check(broken))


def test_empty_passes_without_resolving_is_rejected(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["limitations"].update(passes_without_resolving="  ")
    )
    assert "schema" in codes(check(broken))


def test_missing_outcome_message_is_rejected(site_rule):
    broken = sabotage(site_rule, lambda r: r["outcomes"].pop("not_applicable"))
    assert "schema" in codes(check(broken))


def test_rule_may_not_author_an_error_message(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["outcomes"].update(error={"message": "It broke."})
    )
    assert "schema" in codes(check(broken))


def test_unknown_property_anywhere_is_rejected(site_rule):
    broken = sabotage(site_rule, lambda r: r.update(severty="high"))
    assert "schema" in codes(check(broken))


@pytest.mark.parametrize("outcome", ["unknown", "not_applicable", "invalid_evidence"])
def test_interpolation_in_a_failure_message_is_rejected(site_rule, outcome):
    """These messages print precisely when the value is not there."""
    broken = sabotage(
        site_rule,
        lambda r: r["outcomes"][outcome].update(
            message="The site has {owners.count} owners, which was not collected."
        ),
    )
    assert "schema" in codes(check(broken))


def test_optional_evidence_is_rejected(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["evidence_requirements"][0].update(required=False)
    )
    assert "schema" in codes(check(broken))


def test_unknown_operator_is_rejected(site_rule):
    broken = sabotage(site_rule, lambda r: r["condition"].update(operator="matches"))
    assert "schema" in codes(check(broken))


# ---------------------------------------------------------------------------
# Layer 3: the rule's own graph
# ---------------------------------------------------------------------------


def test_condition_reading_undeclared_evidence_is_rejected(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["condition"].update(evidence="owners.total")
    )
    assert codes(check(broken)) >= {"undeclared-evidence", "undeclared-dependency"}


def test_required_evidence_nobody_consumes_is_rejected(site_rule):
    """The deliberate defect of SPO-LIST-001 v1.0, in miniature."""
    broken = sabotage(
        site_rule,
        lambda r: r["evidence_requirements"].append(
            {
                "path": "permissions.inheritance_broken",
                "type": "boolean",
                "required": True,
            }
        ),
    )
    assert "unused-required-evidence" in codes(check(broken))


def test_the_reviewer_packet_still_carries_the_defect():
    """The packet is frozen. If this goes green, someone regenerated it."""
    import yaml

    from conftest import ROOT

    packet = ROOT / "docs" / "review" / "packet" / "SPO-LIST-001.yaml"
    data = yaml.safe_load(packet.read_text(encoding="utf-8"))
    declared = {r["path"] for r in data["evidence_requirements"]}
    consumed = {data["condition"]["evidence"]}
    if "applicability" in data:
        consumed.add(data["applicability"]["evidence"])
    assert declared - consumed, (
        "the reviewer packet no longer contains the unused required field. "
        "The packet is a frozen copy and must not be regenerated from rules/."
    )


def test_dependency_declared_only_in_a_message_is_still_required(site_rule):
    broken = sabotage(
        site_rule,
        lambda r: r["outcomes"]["pass"].update(
            message="The site has {owners.count} owners, in {region.name}."
        ),
    )
    assert codes(check(broken)) >= {"undeclared-interpolation", "undeclared-dependency"}


# ---------------------------------------------------------------------------
# Layer 4: the repository
# ---------------------------------------------------------------------------


def test_duplicate_id_is_rejected(site_rule):
    from pathlib import Path

    twice = [
        LoadedRule(path=Path("a.yaml"), data=site_rule),
        LoadedRule(path=Path("b.yaml"), data=site_rule),
    ]
    assert "duplicate-id" in codes(validate_repository(twice))


def test_distinct_ids_are_accepted(site_rule, list_rule):
    from pathlib import Path

    both = [
        LoadedRule(path=Path("a.yaml"), data=site_rule),
        LoadedRule(path=Path("b.yaml"), data=list_rule),
    ]
    assert validate_repository(both) == []
