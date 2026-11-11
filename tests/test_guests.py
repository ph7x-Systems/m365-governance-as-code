"""The guests collector, proved against a stand-in service.

CONTRACT-TESTED, and nothing more is claimed: no test here reaches a
directory, and the proof registry holds no record for this collector.
"""

import base64
import json

from m365_governance import collecting, grouping, guests, live_proof, presenting
from m365_governance.graph import GraphReader

TENANT = "https://contoso-admin.sharepoint.com"
AT = "2026-11-11T10:00:00Z"


def _token() -> str:
    body = {"tid": "c0ffee00-0000-4000-8000-000000000001", "roles": ["User.Read.All"]}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _account(number, **over):
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "userType": "Guest",
        "accountEnabled": True,
        "externalUserState": "Accepted",
        "externalUserStateChangeDateTime": "2026-06-01T09:00:00Z",
        "createdDateTime": "2026-05-30T09:00:00Z",
        **over,
    }


def _collect(transport):
    reader = GraphReader(_token(), transport=transport, sleep=lambda _: None)
    return guests.collect(reader, TENANT, AT)


def _tenant(collected):
    return next(d for d in collected.documents if d["resource"]["type"] == "tenant")


def _users(collected):
    return [d for d in collected.documents if d["resource"]["type"] == "user"]


def test_the_request_names_six_properties_and_none_of_them_is_a_person():
    asked = []

    def transport(url, _token):
        asked.append(url)
        return (200, json.dumps({"value": []}), {})

    _collect(transport)
    assert len(asked) == 1
    url = asked[0]
    assert "/v1.0/users?" in url and "userType" in url and "Guest" in url
    selected = url.split("select=")[1].split("&")[0].replace("%2C", ",").split(",")
    assert set(selected) == set(guests.SELECT)
    for personal in (
        "displayName",
        "mail",
        "userPrincipalName",
        "givenName",
        "surname",
        "otherMails",
        "proxyAddresses",
    ):
        assert personal not in url


def test_every_page_is_followed_and_the_count_is_what_was_read():
    pages = {
        "first": {
            "value": [_account(1), _account(2)],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=second",
        },
        "second": {"value": [_account(3)]},
    }

    def transport(url, _token):
        return (200, json.dumps(pages["second" if "skiptoken" in url else "first"]), {})

    collected = _collect(transport)
    assert len(_users(collected)) == 3
    assert _tenant(collected)["facts"]["guests"]["count"]["value"] == 3
    assert collected.complete


def test_no_guests_is_an_observed_zero_and_one_document():
    collected = _collect(lambda url, token: (200, json.dumps({"value": []}), {}))
    assert len(collected.documents) == 1
    count = _tenant(collected)["facts"]["guests"]["count"]
    assert count == {
        "state": "observed",
        "value": 0,
        "raw": {"field": "GET /users (userType eq 'Guest')", "value": 0},
    }


def test_a_refusal_is_not_a_directory_with_no_guests():
    """THE COUNTER-CHECK. A collector that swallowed the 403 would write the
    same single document as an empty directory, with a count of zero."""
    body = {"error": {"code": "Authorization_RequestDenied", "message": "denied"}}
    collected = _collect(lambda url, token: (403, json.dumps(body), {}))
    count = _tenant(collected)["facts"]["guests"]["count"]
    assert count["state"] == "permission-denied" and "value" not in count
    assert not collected.complete
    assert _tenant(collected)["coverage"]["completed"] == []
    assert "guests" in _tenant(collected)["coverage"]["unavailable"]


def test_a_read_that_stops_part_way_keeps_what_it_read_and_publishes_no_total():
    calls = []

    def transport(url, _token):
        calls.append(url)
        if "skiptoken" in url:
            return (403, json.dumps({"error": {"code": "x", "message": "denied"}}), {})
        return (
            200,
            json.dumps(
                {
                    "value": [_account(1), _account(2)],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skiptoken=n",
                }
            ),
            {},
        )

    collected = _collect(transport)
    assert len(_users(collected)) == 2, "what was read before the refusal was dropped"
    count = _tenant(collected)["facts"]["guests"]["count"]
    assert count["state"] != "observed" and "value" not in count
    assert "lower bound" in count["detail"]


def test_a_service_that_ignores_the_filter_does_not_turn_members_into_guests():
    member = _account(9, userType="Member")
    collected = _collect(
        lambda url, token: (200, json.dumps({"value": [_account(1), member]}), {})
    )
    assert [d["resource"]["native_id"] for d in _users(collected)] == [
        _account(1)["id"]
    ]
    count = _tenant(collected)["facts"]["guests"]["count"]
    assert count["state"] == "missing" and "filter" in count["detail"]


def test_a_guest_is_known_by_its_object_id_and_no_document_holds_a_name():
    named = _account(1, displayName="Ana Example", mail="ana@example.org")
    collected = _collect(lambda url, token: (200, json.dumps({"value": [named]}), {}))
    written = json.dumps(collected.documents)
    assert "Ana Example" not in written and "ana@example.org" not in written
    user = _users(collected)[0]
    assert user["resource"]["native_id"] == named["id"]
    assert user["resource"]["display_name"] == named["id"]
    assert set(user["facts"]["guest"]) == set(guests.ADDRESSABLE)


def test_a_property_the_service_did_not_send_is_missing_and_not_false():
    bare = {"id": _account(1)["id"], "userType": "Guest"}
    collected = _collect(lambda url, token: (200, json.dumps({"value": [bare]}), {}))
    facts = _users(collected)[0]["facts"]["guest"]
    assert facts["account_enabled"]["state"] == "missing"
    assert "value" not in facts["account_enabled"]


def test_the_view_shows_one_guest_per_row_with_readable_values():
    collected = _collect(
        lambda url, token: (
            200,
            json.dumps({"value": [_account(1, externalUserState="PendingAcceptance")]}),
            {},
        )
    )
    headers, rows = presenting.table(_users(collected))
    row = dict(zip(headers, rows[0], strict=True))
    assert row["guest.invitation_state"] == "PendingAcceptance"
    assert row["guest.account_enabled"] == "true"


def test_the_command_the_slice_and_the_pending_verification_agree():
    assert grouping.regroup(["entra", "guest", "list"]) == ["collect", "guests"]
    chosen = collecting.SLICES["guests"]
    assert chosen.source == "graph" and chosen.permissions == ("User.Read.All",)
    assert chosen.produces_findings is False
    # TENANT-VERIFICATION-PENDING is not a label somebody typed: it is the
    # registry holding no record.
    assert live_proof.records("guests") == []
    assert live_proof.established_state("guests") == "none"
