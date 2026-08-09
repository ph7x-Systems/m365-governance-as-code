"""R7's invariants: identity, containment and coverage, as executable claims.

The audit proposed `<service>:<type>:<native-id>` as one parsed string. It is
rejected here by falsification rather than by preference, and the reasons are
tests: a site's native identifier IS its URL, and the first field of a colon
split on `https://contoso.sharepoint.com/...` is `https`.

So identity is structured — an explicit workload, an explicit type, an opaque
native identifier and the tenant — and nothing anywhere reads inside the third.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from m365_governance import identity

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "m365_governance" / "data" / "fixtures"


def current_evidence() -> list[dict]:
    return [
        json.loads(Path(f).read_text(encoding="utf-8"))
        for f in sorted(glob.glob(str(FIXTURES / "sharepoint" / "*.json")))
    ]


# ── the falsification ─────────────────────────────────────────────────────


def test_a_parsed_colon_grammar_does_not_survive_a_real_identifier():
    """Why the audit's proposal was not implemented.

    Not a matter of taste. A site's native identifier is a URL, so the first
    field of `<service>:<type>:<native-id>` is `https` and the native id is
    whatever survived two splits. Escaping would be a grammar nobody validates,
    and every consumer would re-implement the parser — the second authority
    this contract exists to remove.
    """
    native = "https://contoso.sharepoint.com/sites/marketing"
    grammar = f"sharepoint:site:{native}"

    service, kind, rest = grammar.split(":", 2)
    assert service == "sharepoint"
    assert kind == "site"
    # And the moment anything splits without a limit — the ordinary mistake,
    # and the one every consumer writing its own parser makes — the identifier
    # is not merely truncated: the third field becomes the URL's SCHEME.
    assert grammar.split(":") == [
        "sharepoint",
        "site",
        "https",
        "//contoso.sharepoint.com/sites/marketing",
    ]
    assert grammar.split(":")[2] == "https"
    assert grammar.split(":")[2] != native


def test_the_native_identifier_is_carried_whole_whatever_is_inside_it():
    """URLs, GUIDs and colon-containing values are all lossless."""
    for native in (
        "https://contoso.sharepoint.com/sites/x",
        "00000000-0000-0000-0000-000000000000",
        "contoso,list,documents",
        "a:b:c:d",
        "spo:site:weird:many:colons",
    ):
        resource = {"workload": "sharepoint", "type": "site", "native_id": native}
        assert identity.ref(resource)["native_id"] == native
        assert identity.key(resource)[2] == native


# ── identity ──────────────────────────────────────────────────────────────


def test_two_workloads_cannot_claim_the_same_resource():
    """A Team and a site can share a URL. Without the namespace they collide."""
    spo = {"workload": "sharepoint", "type": "site", "native_id": "https://x/y"}
    teams = {"workload": "teams", "type": "team", "native_id": "https://x/y"}

    assert identity.key(spo) != identity.key(teams)
    assert not identity.same(spo, teams)


def test_the_same_resource_reached_two_ways_has_one_identity():
    """Identity is the three declared fields and nothing else.

    The same site described with different display metadata — a renamed title,
    a URL recorded with different case in the path — is the same resource, and
    the key says so because neither is part of it.
    """
    once = {
        "workload": "sharepoint",
        "type": "site",
        "native_id": "contoso,site,finance",
        "display_name": "Finance",
        "url": "https://contoso.sharepoint.com/sites/Finance",
    }
    again = {
        "workload": "sharepoint",
        "type": "site",
        "native_id": "contoso,site,finance",
        "display_name": "Finance (renamed)",
        "url": "https://CONTOSO.sharepoint.com/sites/finance",
    }

    assert identity.same(once, again)


def test_identity_does_not_depend_on_what_a_product_calls_something():
    """A name is how a classifier starts lying."""
    resource = {"workload": "sharepoint", "type": "site", "native_id": "n"}
    renamed = dict(resource, display_name="Something Else", url="https://elsewhere")

    assert identity.key(resource) == identity.key(renamed)
    assert "display_name" not in identity.ref(renamed)
    assert "url" not in identity.ref(renamed)


def test_every_current_fixture_carries_a_structured_identity():
    documents = current_evidence()
    assert len(documents) >= 60

    for document in documents:
        resource = document["resource"]
        assert set(identity.FIELDS) <= set(resource)
        assert resource["workload"]
        assert resource["native_id"]
        # The tenant travels with the resource, so identity is self-contained
        # rather than inferred from the document it arrived in.
        assert "host" in resource["tenant"]


def test_an_archived_identity_is_still_readable():
    """A contract with history. The archived document is untouched real history
    and its own schema still ships, so it can be read rather than reinterpreted."""
    archived = FIXTURES / "archive" / "evidence-1.2.0-site.json"
    document = json.loads(archived.read_text(encoding="utf-8"))

    assert document["resource"]["id"], "the old shape is preserved verbatim"
    assert "native_id" not in document["resource"]

    schema = (
        ROOT
        / "src"
        / "m365_governance"
        / "data"
        / "schemas"
        / "archive"
        / "evidence-1.2.0.schema.json"
    )
    assert schema.is_file(), "the contract that reads it must still be held"


# ── containment ───────────────────────────────────────────────────────────


def test_the_tenant_is_the_only_root():
    for document in current_evidence():
        resource = document["resource"]
        if resource["parent"] is None:
            assert resource["type"] == "tenant", (
                f"{resource['native_id']} has no parent and is not a tenant"
            )
        else:
            assert resource["type"] != "tenant"


def test_every_parent_is_a_reference_and_not_a_bare_string():
    for document in current_evidence():
        parent = document["resource"]["parent"]
        if parent is None:
            continue
        assert isinstance(parent, dict)
        assert set(identity.FIELDS) == set(parent)


def test_a_resource_is_never_its_own_parent():
    """The smallest cycle, and the one a copied literal produces."""
    for document in current_evidence():
        resource = document["resource"]
        assert identity.key(resource) != identity.key(resource["parent"] or None) or (
            resource["parent"] is None
        )


def test_containment_walks_upward_and_terminates():
    """No cycles, and every chain ends at a tenant.

    Built across all the fixtures rather than one, because a cycle needs two
    documents to exist and a per-document check would never see it.
    """
    by_key = {}
    for document in current_evidence():
        by_key[identity.key(document["resource"])] = document["resource"]

    for start in by_key.values():
        seen = set()
        node = start
        while node is not None:
            key = identity.key(node)
            assert key not in seen, f"containment cycles at {node['native_id']}"
            seen.add(key)
            parent = node.get("parent")
            if parent is None:
                assert node["type"] == "tenant"
                break
            # A parent outside this evidence set is not a cycle and not a
            # defect: it is a resource nobody collected, and the run set says
            # so rather than inventing it.
            node = by_key.get(identity.key(parent))


def test_a_parent_nobody_collected_is_unobserved_rather_than_invented():
    """The honest third state.

    A list whose site was never collected has a parent that resolves to
    nothing. That is a gap in what was read, and the evidence still declares
    the relationship rather than dropping it — which would have put the
    containment back into prose.
    """
    documents = current_evidence()
    present = {identity.key(d["resource"]) for d in documents}

    dangling = [
        d["resource"]
        for d in documents
        if d["resource"]["parent"]
        and identity.key(d["resource"]["parent"]) not in present
    ]

    # Whatever the number, each one still names its parent completely.
    for resource in dangling:
        assert set(identity.FIELDS) == set(resource["parent"])


# ── coverage is never inferred from containment ───────────────────────────


def test_estate_coverage_is_not_claimed_from_the_documents_that_arrived():
    """R7's coverage rule, stated as the absence of a claim.

    Every observed node having a parent says nothing about whether the estate
    was seen: a collection that read one site of four hundred produces four
    hundredths of an estate in which every node is perfectly contained.

    So no document reports estate completeness, and the run set's own coverage
    stays `not-established` until an inventory universe exists to compare
    against. This test fails the day something starts claiming otherwise
    without one.
    """

    source = (ROOT / "src" / "m365_governance" / "results.py").read_text(
        encoding="utf-8"
    )

    assert "not-established" in source
    # And nothing computes a percentage or a completeness flag from containment.
    for forbidden in ("estate_complete", "coverage_percent", "completeness"):
        assert forbidden not in source


@pytest.mark.parametrize("field", ["workload", "type", "native_id"])
def test_a_reference_missing_any_field_is_not_a_reference(field):
    resource = {"workload": "sharepoint", "type": "site", "native_id": "n"}
    del resource[field]

    with pytest.raises(KeyError):
        identity.ref(resource)


def test_a_comparison_over_several_resources_orders_deterministically():
    """The defect a one-resource example could never show.

    `comparison` sorted its changes by the resource itself. That worked for as
    long as every comparison held ONE resource: a single-element sort never
    compares anything. The first comparison with two resources raised
    `'<' not supported between instances of 'dict' and 'dict'` — in the
    consumer's fixture refresh, not here.

    Identity is a tuple of three fields, which is comparable without anyone
    inventing a separator to join them with.
    """

    changes = [
        {
            "resource": {"workload": "sharepoint", "type": "site", "native_id": "b"},
            "rule": "R2",
            "kind": "changed",
        },
        {
            "resource": {"workload": "sharepoint", "type": "site", "native_id": "a"},
            "rule": "R1",
            "kind": "changed",
        },
        {
            "resource": {"workload": "teams", "type": "team", "native_id": "a"},
            "rule": "R1",
            "kind": "changed",
        },
    ]
    ordered = sorted(changes, key=lambda c: (identity.key(c["resource"]), c["rule"]))

    assert [identity.key(c["resource"]) + (c["rule"],) for c in ordered] == [
        ("sharepoint", "site", "a", "R1"),
        ("sharepoint", "site", "b", "R2"),
        ("teams", "team", "a", "R1"),
    ]
    # And the module really uses that key rather than the reference object.
    source = (ROOT / "src" / "m365_governance" / "comparison.py").read_text(
        encoding="utf-8"
    )
    assert 'identity.key(c["resource"])' in source
    assert 'key=lambda c: (c["resource"]' not in source
