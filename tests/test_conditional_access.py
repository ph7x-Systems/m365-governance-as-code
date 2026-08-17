"""The access-policy slice: what it collects, and what it refuses to imply.

Nothing here reaches a tenant. Every answer Microsoft Graph can give is
supplied by the transport, which is the only way the matrix can be tested at
all: the interesting rows are a `403` from a tenant that granted the permission
but not the directory role, and a `200` carrying an estate that really is empty,
and no live tenant produces both on demand.

THE ONE THING THESE TESTS EXIST FOR: a tenant nobody was allowed to read must
never be readable as a tenant with no Conditional Access. Every other assertion
here is in service of that one surviving the whole path — reader, coverage,
evidence document, manifest.
"""

from __future__ import annotations

import base64
import json

import pytest

from m365_governance import conditional_access, registry
from m365_governance.collecting import SLICES, State
from m365_governance.connecting import tenant_host
from m365_governance.graph import GraphReader
from m365_governance.resources import packaged
from m365_governance.validator import validate_evidence_document

TENANT = "https://contoso-admin.sharepoint.com"
POLICIES = "identity/conditionalAccess/policies"
LOCATIONS = "identity/conditionalAccess/namedLocations"
DEFAULTS = "policies/identitySecurityDefaultsEnforcementPolicy"

SCHEMAS = registry.SchemaRegistry.load(packaged("schemas"))

#: A policy shaped like the ones Microsoft documents, with the authentication
#: strength embedded where the source audit found it.
POLICY = {
    "id": "aaaaaaaa-0000-4000-8000-000000000001",
    "displayName": "Require multifactor authentication for administrators",
    "state": "enabled",
    "conditions": {
        "users": {
            "includeRoles": ["62e90394-69f5-4237-9190-012177145e10"],
            "excludeUsers": ["bbbbbbbb-0000-4000-8000-000000000002"],
        },
        "applications": {"includeApplications": ["All"]},
        "locations": {"includeLocations": ["All"], "excludeLocations": ["AllTrusted"]},
    },
    "grantControls": {
        "operator": "OR",
        "builtInControls": ["mfa"],
        "authenticationStrength": {
            "id": "00000000-0000-0000-0000-000000000004",
            "displayName": "Multifactor authentication",
            "policyType": "builtIn",
            "requirementsSatisfied": "mfa",
            "allowedCombinations": ["fido2", "password,sms"],
        },
    },
}

LOCATION = {
    "@odata.type": "#microsoft.graph.ipNamedLocation",
    "id": "cccccccc-0000-4000-8000-000000000003",
    "displayName": "Documented office range",
    "isTrusted": True,
    "ipRanges": [
        {
            "@odata.type": "#microsoft.graph.iPv4CidrRange",
            "cidrAddress": "198.51.100.0/24",
        }
    ],
}

SECURITY_DEFAULTS = {
    "id": "00000000-0000-0000-0000-000000000005",
    "displayName": "Security Defaults",
    "isEnabled": False,
}


def _token(**claims) -> str:
    """A JWT-shaped string. Unsigned: nothing in this engine verifies one."""
    body = {
        "tid": "11111111-2222-3333-4444-555555555555",
        "roles": ["Policy.Read.All"],
        **claims,
    }
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _reader(transport) -> GraphReader:
    return GraphReader(_token(), transport=transport, sleep=lambda _: None)


def _routed(**answers):
    """A transport that answers by path, so read order is never assumed."""

    def transport(url, token):
        for path, reply in answers.items():
            if path in url:
                return reply
        raise AssertionError(f"nothing was configured for {url}")

    return transport


def _ok(*items):
    return (200, json.dumps({"value": list(items)}), {})


def _one(item):
    return (200, json.dumps(item), {})


def _tenant(**overrides):
    """A transport where everything reads, unless a path is overridden."""
    return _routed(
        **{
            POLICIES: _ok(POLICY),
            LOCATIONS: _ok(LOCATION),
            DEFAULTS: _one(SECURITY_DEFAULTS),
            **overrides,
        }
    )


def _collect(transport):
    return conditional_access.collect(
        _reader(transport), tenant_url=TENANT, observed_at="2026-08-17T00:00:00Z"
    )


# ---------------------------------------------------------------------------
# what it collects
# ---------------------------------------------------------------------------


def test_the_three_areas_are_read_in_one_run():
    collected = _collect(_tenant())

    assert collected.complete
    assert collected.completed == conditional_access.REQUESTED
    assert len(collected.documents) == 3


def test_a_policy_is_carried_whole_and_nothing_is_reshaped():
    """A projection chosen here decides what a future rule may read."""
    collected = _collect(_tenant())

    policy = next(
        d
        for d in collected.documents
        if d["resource"]["type"] == "conditional-access-policy"
    )
    assert policy["facts"]["conditional_access_policies"]["value"] == POLICY


def test_the_authentication_strength_arrives_without_a_fourth_request():
    """The audit's finding, held by a test rather than by a paragraph."""
    asked: list[str] = []

    def transport(url, token):
        asked.append(url)
        return _tenant()(url, token)

    _collect(transport)

    assert not [url for url in asked if "authenticationStrength" in url]
    collected = _collect(_tenant())
    policy = next(
        d
        for d in collected.documents
        if d["resource"]["type"] == "conditional-access-policy"
    )
    strength = policy["facts"]["conditional_access_policies"]["value"]["grantControls"][
        "authenticationStrength"
    ]
    assert strength["requirementsSatisfied"] == "mfa"


def test_unresolved_directory_ids_are_left_exactly_as_they_arrived():
    """Resolving them would be directory-wide inventory, and a bigger claim."""
    collected = _collect(_tenant())

    policy = next(
        d
        for d in collected.documents
        if d["resource"]["type"] == "conditional-access-policy"
    )
    users = policy["facts"]["conditional_access_policies"]["value"]["conditions"][
        "users"
    ]
    assert users["includeRoles"] == ["62e90394-69f5-4237-9190-012177145e10"]
    assert "displayName" not in json.dumps(users)


def test_an_unknown_future_value_survives_without_becoming_a_pass():
    """An enum Microsoft has not shipped yet is carried, not corrected."""
    future = {**POLICY, "state": "unknownFutureValue"}

    collected = _collect(_tenant(**{POLICIES: _ok(future)}))

    document = next(
        d
        for d in collected.documents
        if d["resource"]["type"] == "conditional-access-policy"
    )
    assert document["facts"]["conditional_access_policies"]["value"]["state"] == (
        "unknownFutureValue"
    )


def test_every_document_declares_the_evidence_contract_and_validates():
    for document in _collect(_tenant()).documents:
        assert document["$schema"] == registry.contract("evidence")
        assert validate_evidence_document(document, SCHEMAS) == []


# ---------------------------------------------------------------------------
# the matrix: an empty tenant, and every way of not being one
# ---------------------------------------------------------------------------


def test_an_empty_tenant_is_complete_and_says_so():
    """`200` with `[]`: the tenant has no Conditional Access policy.

    This is the row every other row in this file exists to be distinguished
    from. It is an observation, the coverage is complete, and a rule may decide
    on it.
    """
    collected = _collect(_tenant(**{POLICIES: _ok()}))

    assert collected.complete
    assert "conditional-access-policies" in collected.completed
    assert not [
        d
        for d in collected.documents
        if d["resource"]["type"] == "conditional-access-policy"
    ]


@pytest.mark.parametrize(
    ("status", "state"),
    [
        (403, "permission-denied"),
        (401, "missing"),
        (404, "not-supported"),
        (500, "missing"),
    ],
)
def test_an_area_that_was_refused_is_never_an_empty_tenant(status, state):
    collected = _collect(_tenant(**{POLICIES: (status, "", {})}))

    assert not collected.complete
    assert collected.unavailable["conditional-access-policies"]["state"] == state
    # And the refusal is written down as a document, not only as a coverage
    # entry: a directory holding nothing about an area is a directory somebody
    # will read as a tenant that has none of it.
    refusal = next(d for d in collected.documents if d["resource"]["type"] == "tenant")
    fact = refusal["facts"]["conditional_access_policies"]
    assert fact["state"] == state
    assert "value" not in fact
    assert fact["detail"]


def test_a_delegated_identity_without_a_directory_role_reads_as_permission_denied():
    """`Policy.Read.All` and no accepted role is a denial, not an empty tenant.

    The distinction the tenant made is invisible in the response — both arrive
    as `403` — so the collector records the denial and the detail names the
    directory role, which is what the reader has to act on.
    """
    collected = _collect(_tenant(**{POLICIES: (403, "", {})}))

    detail = collected.unavailable["conditional-access-policies"]["detail"]
    assert "Policy.Read.All" in detail
    assert "directory role" in detail


def test_throttling_is_partial_and_keeps_what_was_read():
    collected = _collect(
        _tenant(**{LOCATIONS: (429, "", {"Retry-After": "0"})}),
    )

    assert collected.unavailable["named-locations"]["state"] == "partial"
    assert "conditional-access-policies" in collected.completed


def test_a_malformed_answer_is_recorded_in_the_contract_vocabulary():
    """`invalid` is a reader state and not one of the four absent states.

    It lands on `missing` — nobody read it — with the reader's own sentence
    kept, rather than being pushed into `permission-denied` because that was
    the nearest word available.
    """
    collected = _collect(_tenant(**{DEFAULTS: (200, "{not json", {})}))

    entry = collected.unavailable["security-defaults"]
    assert entry["state"] == "missing"
    assert "not JSON" in entry["detail"]


def test_one_area_failing_leaves_the_others_intact():
    collected = _collect(_tenant(**{LOCATIONS: (403, "", {})}))

    assert collected.completed == ["conditional-access-policies", "security-defaults"]
    types = {d["resource"]["type"] for d in collected.documents}
    assert "conditional-access-policy" in types
    assert "security-defaults-policy" in types


def test_a_refusal_document_is_valid_evidence_like_any_other():
    for document in _collect(_tenant(**{POLICIES: (403, "", {})})).documents:
        assert validate_evidence_document(document, SCHEMAS) == []


# ---------------------------------------------------------------------------
# coverage, and what the manifest is able to say afterwards
# ---------------------------------------------------------------------------


def test_every_document_carries_the_coverage_of_the_whole_run():
    """Not only its own area.

    A document carrying just its own area would leave the manifest unable to
    report an area that produced no documents at all, and that is precisely the
    area a reader needs told about.
    """
    collected = _collect(_tenant(**{LOCATIONS: (403, "", {})}))

    for document in collected.documents:
        coverage = document["coverage"]
        assert coverage["requested"] == conditional_access.REQUESTED
        assert "named-locations" not in coverage["completed"]
        assert (
            coverage["unavailable"]["named-locations"]["state"] == "permission-denied"
        )


def test_the_run_writes_a_manifest_that_reports_the_denied_area(tmp_path):
    outcome = conditional_access.run(
        token=_token(),
        output=tmp_path,
        tenant_url=TENANT,
        transport=_tenant(**{LOCATIONS: (403, "", {})}),
    )

    assert outcome.state is State.PARTIAL
    manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
    assert manifest["coverage"]["unavailable"]["named-locations"]["state"] == (
        "permission-denied"
    )
    assert manifest["slice"]["name"] == conditional_access.NAME
    assert manifest["identity"]["kind"] == "application"


def test_a_collection_denied_everything_is_partial_and_not_completed(tmp_path):
    """Three refusals are three documents, and the run is not a success."""
    outcome = conditional_access.run(
        token=_token(),
        output=tmp_path,
        tenant_url=TENANT,
        transport=_routed(
            **{
                POLICIES: (403, "", {}),
                LOCATIONS: (403, "", {}),
                DEFAULTS: (403, "", {}),
            }
        ),
    )

    assert outcome.state is State.PARTIAL
    assert len(outcome.written) == 3
    manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
    assert manifest["coverage"]["completed"] == []


def test_two_refused_areas_do_not_overwrite_each_other(tmp_path):
    """Both refusals are about the same tenant resource.

    Named by area rather than by resource for exactly that reason: without it
    the second document would replace the first and the collection would report
    one denial where there were two.
    """
    outcome = conditional_access.run(
        token=_token(),
        output=tmp_path,
        tenant_url=TENANT,
        transport=_tenant(**{POLICIES: (403, "", {}), LOCATIONS: (403, "", {})}),
    )

    assert len({path.name for path in outcome.written}) == len(outcome.written)
    assert len(outcome.written) == 3


def test_no_token_is_a_refusal_that_collected_nothing(tmp_path):
    outcome = conditional_access.run(
        token="", output=tmp_path, tenant_url=TENANT, transport=_tenant()
    )

    assert outcome.state is State.FAILED
    assert outcome.written == []
    assert "never acquires" in outcome.stderr or "no token" in outcome.stderr


# ---------------------------------------------------------------------------
# tenant identity: two questions that must never share a field
# ---------------------------------------------------------------------------


def test_the_observed_tenant_id_comes_from_the_token_and_the_host_from_the_address():
    collected = _collect(_tenant())

    for document in collected.documents:
        tenant = document["provenance"]["tenant"]
        assert tenant["id"] == "11111111-2222-3333-4444-555555555555"
        assert tenant["host"] == "contoso.sharepoint.com"


def test_a_token_that_names_no_directory_leaves_the_id_null():
    """Null says nobody read it. Nothing stands in for it."""
    reader = GraphReader(base64.urlsafe_b64encode(b"{}").decode(), transport=_tenant())
    collected = conditional_access.collect(
        reader, tenant_url=TENANT, observed_at="2026-08-17T00:00:00Z"
    )

    for document in collected.documents:
        assert document["provenance"]["tenant"]["id"] is None
        assert document["provenance"]["identity_kind"] == "not-established"


def test_the_admin_centre_and_the_site_host_are_one_tenant():
    """Two addresses of one organisation must not produce two tenants."""
    assert tenant_host("https://contoso-admin.sharepoint.com") == tenant_host(
        "https://contoso.sharepoint.com/sites/x"
    )
    assert tenant_host("https://contoso-admin.sharepoint.us") == "contoso.sharepoint.us"


def test_two_tenants_are_never_combined():
    """A second collection under a second token stays a second tenant."""
    other = _token(tid="99999999-8888-7777-6666-555555555555")
    reader = GraphReader(other, transport=_tenant())

    collected = conditional_access.collect(
        reader,
        tenant_url="https://fabrikam-admin.sharepoint.com",
        observed_at="2026-08-17T00:00:00Z",
    )

    ids = {d["resource"]["tenant"]["id"] for d in collected.documents}
    hosts = {d["resource"]["tenant"]["host"] for d in collected.documents}
    assert ids == {"99999999-8888-7777-6666-555555555555"}
    assert hosts == {"fabrikam.sharepoint.com"}


def test_no_credential_reaches_any_document():
    token = _token()
    documents = json.dumps(_collect(_tenant()).documents)

    assert token not in documents
    assert "Bearer" not in documents


# ---------------------------------------------------------------------------
# the slice, as the rest of the engine sees it
# ---------------------------------------------------------------------------


def test_the_slice_is_registered_as_a_graph_slice_that_writes_many():
    chosen = SLICES[conditional_access.NAME]

    assert chosen.source == "graph"
    assert chosen.writes_many
    assert not chosen.needs_site
    # An inventory with no rule, and the price of that exception is naming the
    # consumer. Microsoft publishes no normative conclusion about which
    # policies an organisation should have.
    assert not chosen.produces_findings
    assert chosen.consumed_by != "governance rules"


def test_no_mutating_verb_is_reachable_from_this_slice():
    """It reads Graph through the reader, which has no verb to give it."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(conditional_access))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called & {"read", "one"}
    assert not called & {"post", "patch", "put", "delete"}
