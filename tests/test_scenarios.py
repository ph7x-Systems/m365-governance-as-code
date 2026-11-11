"""Composed scenarios: what a join may say, and what it must refuse to."""

import json

import pytest

from m365_governance import scenarios
from m365_governance.cli import main

HOST = "contoso.sharepoint.com"


def _site(name, capability, *, at="2026-11-11T10:00:00Z", state="observed"):
    fact = (
        {"state": "observed", "value": capability}
        if state == "observed"
        else {"state": state, "detail": "refused"}
    )
    return {
        "resource": {
            "workload": "sharepoint",
            "type": "site",
            "native_id": f"https://{HOST}/sites/{name}",
            "tenant": {"id": None, "host": HOST},
            "display_name": name.title(),
            "url": f"https://{HOST}/sites/{name}",
        },
        "provenance": {"collected_at": at, "identity_kind": "delegated"},
        "coverage": {"completed": ["sharing"], "unavailable": {}},
        "facts": {"sharing": {"capability": fact}},
    }


def _enumerated(name):
    document = _site(name, None)
    document["facts"] = {"site": {"template": {"state": "observed", "value": "X"}}}
    return document


def _tenant(capability):
    return {
        "resource": {
            "workload": "sharepoint",
            "type": "tenant",
            "native_id": HOST,
            "tenant": {"id": None, "host": HOST},
        },
        "provenance": {
            "collected_at": "2026-11-11T10:00:00Z",
            "identity_kind": "delegated",
        },
        "coverage": {"completed": ["tenant_sharing"], "unavailable": {}},
        "facts": {
            "tenant_sharing": {"capability": {"state": "observed", "value": capability}}
        },
    }


def _row(inspection, name):
    return next(r for r in inspection["rows"] if r["name"] == name.title())


def test_each_value_means_what_the_reference_says_it_permits():
    inspection = scenarios.external_access(
        [
            _tenant("ExternalUserAndGuestSharing"),
            _site("a", "Disabled"),
            _site("b", "ExistingExternalUserSharingOnly"),
            _site("c", "ExternalUserSharingOnly"),
            _site("d", "ExternalUserAndGuestSharing"),
        ]
    )
    read = {
        r["name"]: (r["external_sharing"], r["new_guests"], r["anonymous_links"])
        for r in inspection["rows"]
    }
    assert read == {
        "A": ("not-permitted", "not-permitted", "not-permitted"),
        "B": ("permitted", "not-permitted", "not-permitted"),
        "C": ("permitted", "permitted", "not-permitted"),
        "D": ("permitted", "permitted", "permitted"),
    }


def test_the_organisation_bounds_the_site_and_the_row_says_so():
    """THE COUNTER-CHECK. An implementation that printed the site's own value
    would call this site open while the organisation forbids it."""
    inspection = scenarios.external_access(
        [_tenant("Disabled"), _site("open", "ExternalUserAndGuestSharing")]
    )
    row = _row(inspection, "open")
    assert row["site_capability"] == "ExternalUserAndGuestSharing"
    assert row["in_force"] == "Disabled"
    assert row["external_sharing"] == "not-permitted"
    assert "organisation" in row["because"]


def test_without_the_organisation_the_bound_is_not_established_and_not_assumed():
    row = _row(scenarios.external_access([_site("solo", "Disabled")]), "solo")
    assert row["organisation_capability"] == "[not-collected]"
    assert row["in_force"] == "Disabled"
    assert "not established" in row["because"]


def test_a_refused_site_is_a_row_and_never_a_site_that_shares_nothing():
    """A refusal is not `Disabled`. Both would otherwise read as a site with
    no external sharing, and only one of them was observed."""
    inspection = scenarios.external_access(
        [
            _tenant("ExternalUserSharingOnly"),
            _site("legal", None, state="permission-denied"),
            _site("closed", "Disabled"),
        ]
    )
    refused = _row(inspection, "legal")
    assert refused["site_capability"] == "[permission-denied]"
    assert refused["in_force"] == "not-established"
    assert refused["external_sharing"] == "not-established"
    assert _row(inspection, "closed")["external_sharing"] == "not-permitted"
    assert inspection["sites"]["by_external_sharing"] == {
        "not-established": 1,
        "not-permitted": 1,
    }


def test_a_site_that_was_enumerated_and_never_read_is_not_dropped():
    inspection = scenarios.external_access(
        [_tenant("Disabled"), _enumerated("ghost"), _site("read", "Disabled")]
    )
    assert inspection["sites"]["in_the_evidence"] == 2
    ghost = _row(inspection, "ghost")
    assert ghost["site_capability"] == "[not-collected]"
    assert ghost["external_sharing"] == "not-established"


def test_an_enumeration_document_never_hides_the_read_of_the_same_site():
    for order in (
        [_enumerated("x"), _site("x", "ExternalUserSharingOnly")],
        [_site("x", "ExternalUserSharingOnly"), _enumerated("x")],
    ):
        inspection = scenarios.external_access(order)
        assert len(inspection["rows"]) == 1
        assert inspection["rows"][0]["in_force"] == "ExternalUserSharingOnly"
        assert inspection["duplicates"] == []


def test_two_reads_of_one_site_use_the_later_and_report_the_duplicate():
    early = _site("x", "ExternalUserAndGuestSharing", at="2026-11-10T10:00:00Z")
    late = _site("x", "Disabled", at="2026-11-11T10:00:00Z")
    for order in ([early, late], [late, early]):
        inspection = scenarios.external_access(order)
        assert len(inspection["rows"]) == 1
        assert inspection["rows"][0]["in_force"] == "Disabled"
        assert inspection["duplicates"] == [f"https://{HOST}/sites/x"]


def test_a_value_with_no_documented_meaning_is_not_guessed():
    row = _row(scenarios.external_access([_site("new", "SomethingNew")]), "new")
    assert row["in_force"] == "not-established"
    assert "documented meaning" in row["because"]


def test_empty_evidence_is_an_empty_inspection_and_not_a_clean_tenant():
    inspection = scenarios.external_access([])
    assert inspection["rows"] == [] and inspection["sites"]["in_the_evidence"] == 0
    text = scenarios.as_text(inspection)
    assert "No SharePoint site is in this evidence." in text


def test_the_inspection_says_what_it_did_not_establish_and_scores_nothing():
    inspection = scenarios.external_access(
        [_tenant("Disabled"), _site("a", "Disabled")]
    )
    assert any("guests exist" in item for item in inspection["not_established"])
    assert inspection["guests"] == {"state": "not-collected"}
    assert any("in fact shared" in item for item in inspection["not_established"])
    text = scenarios.as_text(inspection).lower()
    for word in ("score", "%", "compliant", "pass", "fail", "grade"):
        assert word not in text
    assert inspection["sources"]["digest"].startswith("sha256:")


def test_the_same_evidence_gives_the_same_inspection_in_any_order():
    documents = [_tenant("Disabled"), _site("a", "Disabled"), _site("b", "Disabled")]
    assert scenarios.external_access(documents) == scenarios.external_access(
        list(reversed(documents))
    )


@pytest.fixture
def evidence(tmp_path):
    for index, document in enumerate(
        [_tenant("ExternalUserSharingOnly"), _site("a", "ExternalUserAndGuestSharing")]
    ):
        folder = tmp_path / "ev" / str(index)
        folder.mkdir(parents=True)
        (folder / "doc.json").write_text(json.dumps(document), encoding="utf-8")
        (folder / "collection-manifest.json").write_text("{}", encoding="utf-8")
        (folder / "live-proof-draft.json").write_text("{}", encoding="utf-8")
    return tmp_path / "ev"


def test_the_grouped_command_reads_evidence_and_reaches_nothing(
    evidence, capsys, tmp_path
):
    kept = tmp_path / "out" / "external-access.json"
    code = main(
        [
            "governance",
            "inspect",
            "external-access",
            "--evidence",
            str(evidence),
            "--output",
            "json",
            "--out",
            str(kept),
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(kept.read_text(encoding="utf-8"))
    assert printed["rows"][0]["in_force"] == "ExternalUserSharingOnly"
    assert printed["sources"]["documents"] == 2


def test_csv_and_markdown_are_one_row_per_site(evidence, capsys):
    assert main(["inspect", "external-access", "--evidence", str(evidence)]) == 0
    assert "in force" in capsys.readouterr().out
    main(["inspect", "external-access", "--evidence", str(evidence), "--output", "csv"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split(",")[:3] == ["name", "url", "site_capability"]
    assert len(lines) == 2


def test_no_evidence_is_a_refusal_that_names_what_to_collect(tmp_path, capsys):
    assert main(["inspect", "external-access", "--evidence", str(tmp_path)]) == 2
    assert "sites-sharing" in capsys.readouterr().err
    missing = tmp_path / "nowhere"
    assert main(["inspect", "external-access", "--evidence", str(missing)]) == 2


def _guest(number, *, enabled=True, state="Accepted"):
    return {
        "resource": {
            "workload": "entra",
            "type": "user",
            "native_id": f"00000000-0000-4000-8000-{number:012d}",
            "tenant": {"id": None, "host": HOST},
        },
        "provenance": {"collected_at": "2026-11-11T10:00:00Z"},
        "coverage": {"completed": ["guests"], "unavailable": {}},
        "facts": {
            "guest": {
                "account_enabled": {"state": "observed", "value": enabled},
                "invitation_state": {"state": "observed", "value": state},
            }
        },
    }


def _guest_tenant(count=None, state="observed"):
    fact = (
        {"state": "observed", "value": count}
        if state == "observed"
        else {"state": state, "detail": "ended early"}
    )
    return {
        "resource": {"workload": "entra", "type": "tenant", "native_id": HOST},
        "provenance": {"collected_at": "2026-11-11T10:00:00Z"},
        "coverage": {"completed": [], "unavailable": {}},
        "facts": {"guests": {"count": fact}},
    }


def test_guests_are_counted_by_condition_and_joined_to_no_site():
    """Two facts side by side are not a relation. The inspection must say the
    guests exist and must go on saying that who reaches what was not read."""
    inspection = scenarios.external_access(
        [
            _tenant("ExternalUserSharingOnly"),
            _site("a", "ExternalUserSharingOnly"),
            _guest_tenant(3),
            _guest(1),
            _guest(2, state="PendingAcceptance"),
            _guest(3, enabled=False),
        ]
    )
    assert inspection["guests"] == {
        "state": "observed",
        "accounts_read": 3,
        "accounts_enabled": 2,
        "accounts_disabled": 1,
        "invitations_accepted": 2,
        "invitations_pending": 1,
    }
    assert not any("guests exist" in item for item in inspection["not_established"])
    assert any("can reach which site" in item for item in inspection["not_established"])
    assert any("NOT JOINED" in relation for relation in inspection["relations"])
    assert all("guest" not in row for row in inspection["rows"])
    assert inspection["sources"]["documents"] == 6


def test_a_guest_read_that_ended_early_is_a_lower_bound_and_is_called_one():
    inspection = scenarios.external_access(
        [_site("a", "Disabled"), _guest_tenant(state="permission-denied"), _guest(1)]
    )
    assert inspection["guests"]["state"] == "permission-denied"
    assert inspection["guests"]["accounts_read"] == 1
    assert any("lower bound" in item for item in inspection["not_established"])
    assert "read: permission-denied" in scenarios.as_text(inspection)


def test_the_same_guest_read_twice_is_one_account():
    inspection = scenarios.external_access(
        [_guest_tenant(1), _guest(1), _guest(1, enabled=False)]
    )
    assert inspection["guests"]["accounts_read"] == 1
