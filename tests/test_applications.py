"""The applications collector, proved against a stand-in service.

CONTRACT-TESTED, and nothing more is claimed: no test here reaches a
directory, and the proof registry holds no record for this collector.
"""

import base64
import json

from m365_governance import applications, collecting, grouping, live_proof
from m365_governance.graph import GraphReader

TENANT = "https://contoso-admin.sharepoint.com"
AT = "2026-11-11T10:00:00Z"


def _token() -> str:
    body = {"tid": "c0ffee00-0000-4000-8000-000000000001", "roles": ["x"]}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _app(number, **over):
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "appId": f"00000000-0000-4000-9000-{number:012d}",
        "displayName": f"App {number}",
        "createdDateTime": "2025-03-01T09:00:00Z",
        "signInAudience": "AzureADMyOrg",
        "passwordCredentials": [],
        "keyCredentials": [],
        "requiredResourceAccess": [],
        **over,
    }


def _secret(ends, **over):
    return {
        "keyId": "k",
        "hint": "s3c",
        "secretText": "s3cr3t-value",
        "startDateTime": "2025-12-01T00:00:00Z",
        "endDateTime": ends,
        **over,
    }


def _collect(transport):
    reader = GraphReader(_token(), transport=transport, sleep=lambda _: None)
    return applications.collect(reader, TENANT, AT)


def _answer(*items):
    return lambda url, token: (200, json.dumps({"value": list(items)}), {})


def _facts(collected, index=0):
    documents = [
        d for d in collected.documents if d["resource"]["type"] == "application"
    ]
    return documents[index]["facts"]["application"]


def _tenant(collected):
    return next(d for d in collected.documents if d["resource"]["type"] == "tenant")


def test_nothing_that_is_or_is_part_of_a_secret_is_ever_written():
    """THE COUNTER-CHECK THAT MATTERS MOST. The service returns a hint, the
    first characters of the secret, and a stand-in here returns the secret
    itself. Neither may reach a document."""
    collected = _collect(
        _answer(
            _app(
                1,
                passwordCredentials=[_secret("2026-12-01T00:00:00Z")],
                keyCredentials=[
                    {
                        "key": "MIIC-certificate-bytes",
                        "customKeyIdentifier": "THUMBPRINT00FF",
                        "endDateTime": "2027-01-01T00:00:00Z",
                    }
                ],
            )
        )
    )
    written = json.dumps(collected.documents)
    for forbidden in ("s3c", "s3cr3t-value", "MIIC", "THUMBPRINT00FF", "hint"):
        assert forbidden not in written
    kept = _facts(collected)["credentials"]["value"]
    assert kept == [
        {
            "kind": "secret",
            "starts_at": "2025-12-01T00:00:00Z",
            "ends_at": "2026-12-01T00:00:00Z",
        },
        {"kind": "certificate", "starts_at": None, "ends_at": "2027-01-01T00:00:00Z"},
    ]


def test_the_request_asks_for_no_certificate_bytes_and_no_owners():
    asked = []

    def transport(url, _token):
        asked.append(url)
        return (200, json.dumps({"value": []}), {})

    _collect(transport)
    selected = asked[0].split("select=")[1].split("&")[0].replace("%2C", ",").split(",")
    assert set(selected) == set(applications.SELECT)
    assert "owners" not in asked[0] and "$expand" not in asked[0]


def test_the_earliest_end_is_the_first_credential_to_stop_working():
    collected = _collect(
        _answer(
            _app(
                1,
                passwordCredentials=[
                    _secret("2027-03-01T00:00:00Z"),
                    _secret("2026-11-20T00:00:00Z"),
                ],
            )
        )
    )
    facts = _facts(collected)
    assert facts["secrets"]["value"] == 2 and facts["certificates"]["value"] == 0
    assert facts["earliest_credential_end"]["value"] == "2026-11-20T00:00:00Z"


def test_no_credentials_is_an_observed_zero_and_has_no_end_to_report():
    facts = _facts(_collect(_answer(_app(1))))
    assert facts["secrets"] == {
        "state": "observed",
        "value": 0,
        "raw": {"field": "passwordCredentials", "value": 0},
    }
    assert facts["credentials"]["value"] == []
    assert "earliest_credential_end" not in facts


def test_a_credential_list_the_service_did_not_send_is_missing_and_not_empty():
    """Absent is not zero: an application whose secrets were not returned must
    not be read as an application with nothing to expire."""
    bare = _app(1)
    del bare["passwordCredentials"]
    facts = _facts(_collect(_answer(bare)))
    assert facts["secrets"]["state"] == "missing"
    assert facts["credentials"]["state"] == "missing"
    assert facts["certificates"]["state"] == "observed"
    assert "earliest_credential_end" not in facts


def test_what_is_asked_for_is_counted_by_kind_and_never_called_granted():
    asks = [
        {
            "resourceAppId": "r",
            "resourceAccess": [
                {"id": "1", "type": "Role"},
                {"id": "2", "type": "Scope"},
                {"id": "3", "type": "Scope"},
            ],
        }
    ]
    facts = _facts(_collect(_answer(_app(1, requiredResourceAccess=asks))))
    assert facts["requested_application_permissions"]["value"] == 1
    assert facts["requested_delegated_permissions"]["value"] == 2
    assert not any("grant" in name or "consent" in name for name in facts)


def test_paging_is_followed_and_a_refusal_is_not_an_empty_directory():
    def paged(url, _token):
        if "skiptoken" in url:
            return (200, json.dumps({"value": [_app(2)]}), {})
        return (
            200,
            json.dumps(
                {
                    "value": [_app(1)],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/applications?$skiptoken=n",
                }
            ),
            {},
        )

    assert _tenant(_collect(paged))["facts"]["applications"]["count"]["value"] == 2

    denied = _collect(
        lambda url, token: (
            403,
            json.dumps({"error": {"code": "x", "message": "denied"}}),
            {},
        )
    )
    count = _tenant(denied)["facts"]["applications"]["count"]
    assert count["state"] == "permission-denied" and "value" not in count


def test_the_command_the_slice_and_the_pending_verification_agree():
    assert grouping.regroup(["entra", "app", "list"]) == ["collect", "applications"]
    chosen = collecting.SLICES["applications"]
    assert chosen.source == "graph"
    assert chosen.permissions == ("Application.Read.All",)
    assert live_proof.records("applications") == []
