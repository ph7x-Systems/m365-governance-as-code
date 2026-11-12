"""The service principals collector, proved against a stand-in service.

CONTRACT-TESTED, and nothing more is claimed: no test here reaches a
directory.
"""

import base64
import json

from m365_governance import collecting, grouping, service_principals
from m365_governance.graph import GraphReader

TENANT = "https://contoso-admin.sharepoint.com"
AT = "2026-11-12T10:00:00Z"
HOME = "c0ffee00-0000-4000-8000-000000000001"


def _token(tid=HOME) -> str:
    body = {"roles": ["x"], **({"tid": tid} if tid else {})}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _principal(number, **over):
    return {
        "id": f"sp-{number}",
        "appId": f"app-{number}",
        "displayName": f"Principal {number}",
        "servicePrincipalType": "Application",
        "accountEnabled": True,
        "appOwnerOrganizationId": HOME,
        "passwordCredentials": [],
        "keyCredentials": [],
        **over,
    }


def _collect(*items, token=None, status=200):
    body = {"value": list(items)} if status == 200 else {"error": {"message": "no"}}
    reader = GraphReader(
        token or _token(),
        transport=lambda url, t: (status, json.dumps(body), {}),
        sleep=lambda _: None,
    )
    return service_principals.collect(reader, TENANT, AT)


def _facts(collected, identifier):
    return next(
        d["facts"]["service_principal"]
        for d in collected.documents
        if d["resource"]["native_id"] == identifier
    )


def test_whose_application_it_is_comes_from_two_identifiers_and_never_a_name():
    """THE COUNTER-CHECK. A vendor's application named like one of ours is
    still the vendor's, and one of ours with an odd name is still ours."""
    collected = _collect(
        _principal(1, displayName="Microsoft Graph"),
        _principal(2, displayName="Payroll", appOwnerOrganizationId="other-org"),
        _principal(3, appOwnerOrganizationId=HOME.upper()),
    )
    assert _facts(collected, "sp-1")["owned_by_this_directory"]["value"] is True
    assert _facts(collected, "sp-2")["owned_by_this_directory"]["value"] is False
    assert _facts(collected, "sp-3")["owned_by_this_directory"]["value"] is True


def test_ownership_is_not_guessed_when_either_identifier_is_missing():
    bare = _principal(1)
    del bare["appOwnerOrganizationId"]
    assert _facts(_collect(bare), "sp-1")["owned_by_this_directory"]["state"] == (
        "missing"
    )
    no_directory = _collect(_principal(1), token=_token(tid=None))
    assert _facts(no_directory, "sp-1")["owned_by_this_directory"]["state"] == (
        "missing"
    )


def test_a_disabled_principal_is_said_to_be_disabled_and_silence_is_not_enabled():
    silent = _principal(2)
    del silent["accountEnabled"]
    collected = _collect(_principal(1, accountEnabled=False), silent)
    assert _facts(collected, "sp-1")["account_enabled"]["value"] is False
    assert _facts(collected, "sp-2")["account_enabled"]["state"] == "missing"


def test_nothing_that_is_or_is_part_of_a_secret_is_ever_written():
    collected = _collect(
        _principal(
            1,
            passwordCredentials=[
                {
                    "hint": "s3c",
                    "secretText": "s3cr3t",
                    "endDateTime": "2027-01-01T00:00:00Z",
                }
            ],
        )
    )
    written = json.dumps(collected.documents)
    assert "s3c" not in written and '"hint"' not in written
    facts = _facts(collected, "sp-1")
    assert facts["earliest_credential_end"]["value"] == "2027-01-01T00:00:00Z"


def test_a_refused_read_is_not_a_directory_with_no_service_principals():
    collected = _collect(status=403)
    count = collected.documents[0]["facts"]["service_principals"]["count"]
    assert count["state"] == "permission-denied" and "value" not in count
    assert "Application.Read.All" in count["detail"]


def test_the_command_and_the_slice_agree():
    assert grouping.regroup(["entra", "serviceprincipal", "list"]) == [
        "collect",
        "service-principals",
    ]
    chosen = collecting.SLICES["service-principals"]
    assert chosen.permissions == ("Application.Read.All",)
    assert chosen.source == "graph" and chosen.produces_findings is False
