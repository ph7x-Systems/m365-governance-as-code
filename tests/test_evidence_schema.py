"""The evidence schema, and what a collector may not hand over."""

from __future__ import annotations

import json

import pytest

from conftest import EVIDENCE_FIXTURES, evidence, sabotage
from m365_governance.validator import validate_evidence_document


def problems(document: dict) -> list:
    return validate_evidence_document(document, "<test>")


@pytest.mark.parametrize("path", EVIDENCE_FIXTURES, ids=lambda p: p.stem)
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


# ---------------------------------------------------------------------------
# imported evidence
# ---------------------------------------------------------------------------


def test_the_imported_fixture_is_valid():
    assert problems(evidence("site-imported-inventory")) == []


def test_imported_evidence_must_name_who_exported_it():
    """Without it, an import is indistinguishable from a collection we ran."""
    broken = sabotage(
        evidence("site-imported-inventory"),
        lambda d: d["provenance"].pop("import_source"),
    )
    assert problems(broken)


def test_imported_evidence_may_not_carry_scopes():
    """`scopes: []` on an import reads as 'no permissions were needed' rather
    than 'this does not apply'."""
    broken = sabotage(
        evidence("site-imported-inventory"),
        lambda d: d["provenance"].update(scopes=["Sites.Read.All"]),
    )
    assert problems(broken)


def test_a_live_run_may_not_carry_an_import_source():
    broken = sabotage(
        evidence("site-two-owners"),
        lambda d: d["provenance"].update(
            import_source={"tool": "ShareGate", "exported_at": "2026-01-01T00:00:00Z"}
        ),
    )
    assert problems(broken)


def test_a_collected_run_still_needs_its_scopes_and_tenant():
    for field in ("scopes", "tenant", "source_api"):
        broken = sabotage(
            evidence("site-two-owners"), lambda d, f=field: d["provenance"].pop(f)
        )
        assert problems(broken), f"a collected run without {field} was accepted"


def test_acquisition_is_required_and_separate_from_identity():
    """They were one field, and the conditional rules that govern `scopes` and
    `import_source` were keyed on the answer to a different question: who
    observed this, rather than how it got here. An import that named its
    collecting identity could not be expressed at all."""
    broken = sabotage(
        evidence("site-two-owners"), lambda d: d["provenance"].pop("acquisition")
    )
    assert problems(broken)

    # The two vocabularies do not overlap, and neither accepts the other's
    # words. `imported` as an identity is what this replaced.
    for field, value in (
        ("identity_kind", "imported"),
        ("identity_kind", "collected"),
        ("acquisition", "delegated"),
    ):
        broken = sabotage(
            evidence("site-two-owners"),
            lambda d, f=field, v=value: d["provenance"].update({f: v}),
        )
        assert problems(broken), f"{field}={value} was accepted"


def test_an_import_carries_no_scopes_of_ours():
    """`scopes: []` would read as 'no permissions were needed' rather than
    'this does not apply', and those are opposite claims."""
    broken = sabotage(
        evidence("site-imported-inventory"),
        lambda d: d["provenance"].update(scopes=["Sites.Read.All"]),
    )
    assert problems(broken)


def test_a_tenant_carries_an_identity_and_an_address():
    """A hostname is an endpoint. Requiring the id and allowing it to be null
    is the difference between `nobody read this` and `nobody meant this field
    to exist`."""
    for field in ("id", "host"):
        broken = sabotage(
            evidence("site-two-owners"),
            lambda d, f=field: d["provenance"]["tenant"].pop(f),
        )
        assert problems(broken), f"a tenant without {field} was accepted"

    # Null is a permitted answer for the id and never for the address.
    assert problems(
        sabotage(
            evidence("site-two-owners"),
            lambda d: d["provenance"]["tenant"].update(host=None),
        )
    )
    assert not problems(
        sabotage(
            evidence("site-two-owners"),
            lambda d: d["provenance"]["tenant"].update(id=None),
        )
    )


def test_an_import_needs_a_tool_and_a_date():
    for field in ("tool", "exported_at"):
        broken = sabotage(
            evidence("site-imported-inventory"),
            lambda d, f=field: d["provenance"]["import_source"].pop(f),
        )
        assert problems(broken), f"an import without {field} was accepted"


def test_an_unknown_identity_kind_is_rejected():
    broken = sabotage(
        evidence("site-two-owners"),
        lambda d: d["provenance"].update(identity_kind="trust-me"),
    )
    assert problems(broken)
