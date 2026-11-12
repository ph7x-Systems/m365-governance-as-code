"""The groups collector, proved against a stand-in service.

CONTRACT-TESTED, and nothing more is claimed: no test here reaches a
directory, and the proof registry holds no record for this collector.
"""

import base64
import json

from m365_governance import collecting, grouping, groups, live_proof
from m365_governance.graph import GraphReader

TENANT = "https://contoso-admin.sharepoint.com"
AT = "2026-11-12T10:00:00Z"
USER = "#microsoft.graph.user"
PRINCIPAL = "#microsoft.graph.servicePrincipal"


def _token() -> str:
    body = {"tid": "c0ffee00-0000-4000-8000-000000000001", "roles": ["x"]}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _group(number, **over):
    return {
        "id": f"group-{number}",
        "displayName": f"Group {number}",
        "createdDateTime": "2025-02-01T09:00:00Z",
        "visibility": "Private",
        "resourceProvisioningOptions": [],
        **over,
    }


def _people(*kinds):
    return [
        {"@odata.type": k, "id": f"p{n}", "displayName": f"Person {n}"}
        for n, k in enumerate(kinds)
    ]


def _service(listed, owners=None, members=None, refuse=()):
    owners, members = owners or {}, members or {}
    asked = []

    def transport(url, _token):
        asked.append(url)
        for identifier in [g["id"] for g in listed]:
            for kind, table in (("owners", owners), ("members", members)):
                if f"/groups/{identifier}/{kind}" in url:
                    if (identifier, kind) in refuse:
                        body = {"error": {"code": "x", "message": "denied"}}
                        return (403, json.dumps(body), {})
                    return (200, json.dumps({"value": table.get(identifier, [])}), {})
        return (200, json.dumps({"value": listed}), {})

    transport.asked = asked
    return transport


def _collect(transport):
    reader = GraphReader(_token(), transport=transport, sleep=lambda _: None)
    return groups.collect(reader, TENANT, AT)


def _facts(collected, identifier):
    return next(
        d["facts"]["group"]
        for d in collected.documents
        if d["resource"]["native_id"] == identifier
    )


def test_only_microsoft_365_groups_are_asked_for_and_only_ids_of_people():
    transport = _service([_group(1)])
    _collect(transport)
    first, *rest = transport.asked
    assert "groupTypes" in first and "Unified" in first
    assert len(rest) == 2
    for url in rest:
        assert "select=id" in url.replace("%24", "$").replace("$", "")
        for personal in ("displayName", "mail", "userPrincipalName"):
            assert personal not in url


def test_owners_and_members_are_counts_by_kind_and_never_names():
    """A service that sends names anyway must not get them into evidence."""
    collected = _collect(
        _service(
            [_group(1)],
            owners={"group-1": _people(USER, PRINCIPAL)},
            members={"group-1": _people(USER, USER, USER)},
        )
    )
    facts = _facts(collected, "group-1")
    assert (facts["owners"]["value"], facts["user_owners"]["value"]) == (2, 1)
    assert (facts["members"]["value"], facts["user_members"]["value"]) == (3, 3)
    written = json.dumps(collected.documents)
    assert "Person 0" not in written and '"p0"' not in written


def test_a_group_with_no_owner_is_an_observed_zero():
    facts = _facts(_collect(_service([_group(1)])), "group-1")
    assert facts["owners"] == {"state": "observed", "value": 0}
    assert facts["user_owners"] == {"state": "observed", "value": 0}


def test_owners_that_were_refused_are_not_a_group_with_no_owner():
    """THE COUNTER-CHECK. Swallowing the refusal would publish zero owners
    for a group that has some, which is the worst answer this can give."""
    collected = _collect(
        _service(
            [_group(1), _group(2)],
            owners={"group-2": _people(USER)},
            refuse={("group-1", "owners")},
        )
    )
    refused = _facts(collected, "group-1")
    assert refused["owners"]["state"] == "permission-denied"
    assert "value" not in refused["owners"]
    assert refused["members"]["state"] == "observed"
    assert _facts(collected, "group-2")["owners"]["value"] == 1
    tenant = next(d for d in collected.documents if d["resource"]["type"] == "tenant")
    assert tenant["coverage"]["completed"] == []
    assert tenant["coverage"]["unavailable"]["groups"]["state"] == "partial"
    assert tenant["facts"]["groups"]["count"]["value"] == 2


def test_a_team_is_a_group_that_says_so_and_silence_is_not_no():
    collected = _collect(
        _service(
            [
                _group(1, resourceProvisioningOptions=["Team"]),
                _group(2),
                {"id": "group-3", "displayName": "Bare"},
            ]
        )
    )
    assert _facts(collected, "group-1")["is_team"]["value"] is True
    assert _facts(collected, "group-2")["is_team"]["value"] is False
    assert _facts(collected, "group-3")["is_team"]["state"] == "missing"


def test_a_refused_listing_is_not_a_directory_with_no_groups():
    def denied(url, token):
        return (403, json.dumps({"error": {"code": "x", "message": "denied"}}), {})

    collected = _collect(denied)
    count = collected.documents[0]["facts"]["groups"]["count"]
    assert count["state"] == "permission-denied" and "value" not in count
    assert len(collected.documents) == 1


def test_the_command_the_slice_and_the_pending_verification_agree():
    assert grouping.regroup(["entra", "group", "list"]) == ["collect", "groups"]
    chosen = collecting.SLICES["groups"]
    assert chosen.source == "graph"
    assert chosen.permissions == ("GroupMember.Read.All",)
    assert live_proof.established_state("groups") == "full"
