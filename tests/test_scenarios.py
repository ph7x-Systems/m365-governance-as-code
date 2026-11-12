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


# --- ownership -----------------------------------------------------------------


def _owned(name, *, named=0, groups=0, state="observed", at="2026-11-11T10:00:00Z"):
    document = _site(name, "Disabled", at=at)
    if state == "observed":
        owners = {
            "state": "observed",
            "direct": [{"principal_id": f"u{n}"} for n in range(named)],
            "groups": [{"principal_id": f"g{n}"} for n in range(groups)],
            "direct_count": {"state": "observed", "value": named},
            "group_count": {"state": "observed", "value": groups},
        }
    else:
        owners = {"state": state, "detail": "not said"}
    document["facts"] = {"owners": owners}
    return document


def _standing(inspection, name):
    return _row(inspection, name)["standing"]


def test_a_site_is_compared_with_the_number_the_operator_chose():
    documents = [
        _owned("one", named=1),
        _owned("two", named=2),
        _owned("three", named=3),
    ]
    default = scenarios.ownership(documents)
    assert [_standing(default, n) for n in ("one", "two", "three")] == [
        "fewer",
        "meets",
        "meets",
    ]
    assert default["parameters"] == {"minimum_owners": 2}
    stricter = scenarios.ownership(documents, minimum_owners=3)
    assert [_standing(stricter, n) for n in ("one", "two", "three")] == [
        "fewer",
        "fewer",
        "meets",
    ]


def test_a_group_is_never_counted_as_one_person_or_as_none():
    """THE COUNTER-CHECK. Counting a group as one would call the first site
    sufficient; ignoring it would call it short. Neither was observed."""
    inspection = scenarios.ownership(
        [_owned("mixed", named=1, groups=1), _owned("covered", named=2, groups=1)]
    )
    mixed = _row(inspection, "mixed")
    assert mixed["standing"] == "not-established"
    assert "members were not read" in mixed["because"]
    assert _standing(inspection, "covered") == "at-least"


def test_a_site_that_did_not_answer_is_not_a_site_without_administrators():
    inspection = scenarios.ownership(
        [
            _owned("refused", state="permission-denied"),
            _owned("silent", state="partial"),
            _owned("named", named=1),
        ]
    )
    for name, state in (("refused", "permission-denied"), ("silent", "partial")):
        row = _row(inspection, name)
        assert row["owners_read"] == f"[{state}]"
        assert row["standing"] == "not-established"
        assert row["named_administrators"] == ""
    assert inspection["sites"]["by_standing"] == {"fewer": 1, "not-established": 2}


def test_a_site_with_no_owner_read_is_kept_and_duplicates_use_the_later():
    early = _owned("x", named=1, at="2026-11-10T10:00:00Z")
    late = _owned("x", named=2, at="2026-11-11T10:00:00Z")
    inspection = scenarios.ownership([_enumerated("ghost"), early, late])
    assert inspection["sites"]["in_the_evidence"] == 2
    assert _row(inspection, "ghost")["owners_read"] == "[not-collected]"
    assert _standing(inspection, "x") == "meets"
    assert inspection["duplicates"] == [f"https://{HOST}/sites/x"]


def test_ownership_says_what_an_administrator_is_not_and_scores_nothing():
    inspection = scenarios.ownership([_owned("a", named=2)])
    said = " ".join(inspection["not_established"])
    assert "group owner" in said and "team" in said
    text = scenarios.as_text(inspection).lower()
    for word in ("score", "%", "compliant", "pass", "fail", "grade", "orphan"):
        assert word not in text
    assert scenarios.as_text(scenarios.ownership([])).count("collected") == 0


def test_the_ownership_command_takes_the_threshold_and_refuses_nonsense(
    tmp_path, capsys
):
    folder = tmp_path / "ev"
    folder.mkdir()
    (folder / "a.json").write_text(json.dumps(_owned("a", named=1)), encoding="utf-8")
    base = ["governance", "inspect", "ownership", "--evidence", str(folder)]
    assert main([*base, "--output", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"][0]["standing"] == "fewer"
    assert main([*base, "--minimum-owners", "1", "--output", "csv"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("name,url,owners_read") and ",meets," in lines[1]
    assert main([*base, "--minimum-owners", "0"]) == 2


# --- application exposure --------------------------------------------------------


def _registered(
    number, ends=(), *, at="2026-11-11T10:00:00Z", listed=True, asks=(1, 2)
):
    credentials = (
        {
            "state": "observed",
            "value": [
                {"kind": "secret", "starts_at": None, "ends_at": e} for e in ends
            ],
        }
        if listed
        else {"state": "missing", "detail": "not returned"}
    )
    return {
        "resource": {
            "workload": "entra",
            "type": "application",
            "native_id": f"app-{number}",
            "display_name": f"App {number}",
        },
        "provenance": {"collected_at": at, "identity_kind": "application"},
        "coverage": {"completed": ["applications"], "unavailable": {}},
        "facts": {
            "application": {
                "app_id": {"state": "observed", "value": f"client-{number}"},
                "credentials": credentials,
                "requested_application_permissions": {
                    "state": "observed",
                    "value": asks[0],
                },
                "requested_delegated_permissions": {
                    "state": "observed",
                    "value": asks[1],
                },
            }
        },
    }


def _exposed(inspection, number):
    return next(r for r in inspection["rows"] if r["native_id"] == f"app-{number}")


def test_a_credential_is_placed_relative_to_when_the_evidence_was_collected():
    inspection = scenarios.app_exposure(
        [
            _registered(1, ["2026-11-01T00:00:00Z"]),
            _registered(2, ["2026-11-25T00:00:00Z"]),
            _registered(3, ["2027-06-01T00:00:00Z"]),
            _registered(4, []),
        ]
    )
    assert [_exposed(inspection, n)["standing"] for n in (1, 2, 3, 4)] == [
        "ended",
        "ending",
        "later",
        "no-credentials",
    ]
    assert inspection["parameters"] == {"expires_within_days": 30}
    assert _exposed(inspection, 2)["earliest_end"] == "2026-11-25T00:00:00Z"


def test_the_answer_does_not_change_with_the_day_it_is_asked():
    """THE COUNTER-CHECK. An implementation that measured from the clock would
    call this credential ended; the evidence is from 2020 and it had a week
    left when it was read."""
    old = _registered(1, ["2020-01-08T00:00:00Z"], at="2020-01-01T00:00:00Z")
    row = _exposed(scenarios.app_exposure([old]), 1)
    assert row["standing"] == "ending"
    assert row["collected_at"] == "2020-01-01T00:00:00Z"


def test_the_window_is_the_operators():
    documents = [_registered(1, ["2026-12-30T00:00:00Z"])]
    assert _exposed(scenarios.app_exposure(documents), 1)["standing"] == "later"
    wider = scenarios.app_exposure(documents, expires_within_days=60)
    assert _exposed(wider, 1)["standing"] == "ending"


def test_credentials_that_were_not_returned_are_not_an_application_with_none():
    inspection = scenarios.app_exposure(
        [_registered(1, listed=False), _registered(2, [])]
    )
    assert _exposed(inspection, 1)["standing"] == "not-established"
    assert _exposed(inspection, 2)["standing"] == "no-credentials"
    assert inspection["applications"]["by_standing"] == {
        "no-credentials": 1,
        "not-established": 1,
    }


def test_one_ended_credential_is_reported_even_beside_a_healthy_one():
    row = _exposed(
        scenarios.app_exposure(
            [_registered(1, ["2026-01-01T00:00:00Z", "2028-01-01T00:00:00Z"])]
        ),
        1,
    )
    assert (row["standing"], row["ended"], row["ending"], row["later"]) == (
        "ended",
        1,
        0,
        1,
    )


def test_what_is_asked_for_is_shown_and_never_called_granted():
    inspection = scenarios.app_exposure([_registered(1, [], asks=(3, 0))])
    assert _exposed(inspection, 1)["requested_application_permissions"] == 3
    assert any("NOT JOINED" in r for r in inspection["relations"])
    assert any("in fact granted" in item for item in inspection["not_established"])
    text = scenarios.as_text(inspection)
    assert "asked, not granted" in text
    for word in ("score", "%", "compliant", "risk level", "grade"):
        assert word not in text.lower()


def test_the_exposure_command_takes_a_window_in_days(tmp_path, capsys):
    folder = tmp_path / "ev"
    folder.mkdir()
    (folder / "a.json").write_text(
        json.dumps(_registered(1, ["2026-12-30T00:00:00Z"])), encoding="utf-8"
    )
    base = ["governance", "inspect", "app-exposure", "--evidence", str(folder)]
    assert main([*base, "--output", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"][0]["standing"] == "later"
    assert main([*base, "--expires-within", "60d", "--output", "csv"]) == 0
    assert ",ending," in capsys.readouterr().out
    assert main([*base, "--expires-within", "soon"]) == 2


# --- conditional access coverage --------------------------------------------------


def _policy(name, *, state="enabled", users=None, extra=None, controls=("mfa",)):
    definition = {
        "id": f"policy-{name}",
        "displayName": name,
        "state": state,
        "conditions": {
            "users": users or {"includeUsers": ["All"]},
            "applications": {"includeApplications": ["All"]},
            "clientAppTypes": ["all"],
            **(extra or {}),
        },
        "grantControls": {"operator": "OR", "builtInControls": list(controls)},
    }
    return {
        "resource": {
            "workload": "entra",
            "type": "conditional-access-policy",
            "native_id": f"policy-{name}",
            "display_name": name,
        },
        "provenance": {"collected_at": "2026-11-11T10:00:00Z"},
        "coverage": {"completed": ["conditional_access_policies"], "unavailable": {}},
        "facts": {
            "conditional_access_policies": {
                "policy": {"state": "observed", "value": definition}
            }
        },
    }


def _covered(inspection, name):
    return next(r for r in inspection["rows"] if r["name"] == name)


def test_a_policy_that_only_reports_is_never_shown_as_enforced():
    """THE COUNTER-CHECK. Three policies name every user; one of them does
    something at sign-in."""
    inspection = scenarios.ca_coverage(
        [
            _policy("on"),
            _policy("report", state="enabledForReportingButNotEnforced"),
            _policy("off", state="disabled"),
            _policy("odd", state="somethingNew"),
        ]
    )
    assert {r["name"]: r["in_force"] for r in inspection["rows"]} == {
        "on": "enforced",
        "report": "report-only",
        "off": "off",
        "odd": "not-established",
    }
    assert inspection["policies"]["by_in_force"]["enforced"] == 1


def test_the_scope_is_what_the_definition_names_and_exclusions_are_counted():
    inspection = scenarios.ca_coverage(
        [
            _policy(
                "all",
                users={
                    "includeUsers": ["All"],
                    "excludeUsers": ["u1"],
                    "excludeGroups": ["g1", "g2"],
                },
            ),
            _policy(
                "some",
                users={
                    "includeUsers": ["None"],
                    "includeGroups": ["g1"],
                    "includeRoles": ["r1"],
                },
            ),
            _policy("none", users={"includeUsers": ["None"]}),
            _policy("guests", users={"includeUsers": ["GuestsOrExternalUsers"]}),
        ]
    )
    everyone = _covered(inspection, "all")
    assert everyone["static_scope"] == "every user, with exclusions"
    assert (everyone["excludes_users"], everyone["excludes_groups"]) == (1, 2)
    some = _covered(inspection, "some")
    assert some["static_scope"] == "named principals"
    assert (some["includes_groups"], some["includes_roles"]) == (1, 1)
    assert _covered(inspection, "none")["static_scope"] == "nobody"
    assert _covered(inspection, "guests")["includes_guests"] is True


def test_a_condition_that_narrows_a_policy_is_named_and_one_that_does_not_is_not():
    inspection = scenarios.ca_coverage(
        [
            _policy("plain"),
            _policy(
                "narrow",
                extra={
                    "locations": {"includeLocations": ["AllTrusted"]},
                    "platforms": {"includePlatforms": ["iOS"]},
                    "applications": {"includeApplications": ["one-app"]},
                    "clientAppTypes": ["browser"],
                },
            ),
        ]
    )
    assert _covered(inspection, "plain")["narrowed_by"] == "nothing else"
    assert _covered(inspection, "narrow")["narrowed_by"] == (
        "applications, locations, platforms, clientAppTypes"
    )


def test_one_policy_can_be_asked_for_and_a_wrong_id_is_said_so():
    documents = [_policy("a"), _policy("b")]
    one = scenarios.ca_coverage(documents, policy_id="policy-b")
    assert [r["name"] for r in one["rows"]] == ["b"]
    assert one["policies"] == {
        "in_the_evidence": 2,
        "shown": 1,
        "by_in_force": {"enforced": 1},
        "read_refused": False,
    }
    wrong = scenarios.ca_coverage(documents, policy_id="policy-z")
    assert wrong["rows"] == []
    assert "no policy with that id" in wrong["not_established"][0]
    text = scenarios.as_text(wrong)
    assert "No Conditional Access policy is in this evidence." not in text
    assert "Nothing in this evidence matches what was asked for." in text
    assert "  id               policy-b" in scenarios.as_text(one)


def test_a_refused_read_is_not_a_tenant_with_no_policy():
    refusal = {
        "resource": {"workload": "entra", "type": "tenant", "native_id": HOST},
        "provenance": {"collected_at": "2026-11-11T10:00:00Z"},
        "coverage": {"completed": [], "unavailable": {}},
        "facts": {
            "conditional_access_policies": {
                "state": "permission-denied",
                "detail": "denied",
            }
        },
    }
    inspection = scenarios.ca_coverage([refusal])
    assert inspection["rows"] == [] and inspection["policies"]["read_refused"]
    assert "not a tenant with no policy" in inspection["not_established"][0]


def test_coverage_never_claims_who_a_policy_applies_to():
    inspection = scenarios.ca_coverage([_policy("a")])
    said = " ".join(inspection["not_established"])
    assert "given sign-in" in said and "outside every policy" in said
    text = scenarios.as_text(inspection).lower()
    for word in ("score", "%", "compliant", "protected", "covered users", "grade"):
        assert word not in text


def test_the_packaged_policy_fixtures_are_read_as_they_are(capsys):
    from m365_governance import collecting

    fixtures = collecting.COLLECTOR.parents[3] / "fixtures" / "entra"
    assert (
        main(
            [
                "governance",
                "inspect",
                "ca-coverage",
                "--evidence",
                str(fixtures),
                "--output",
                "json",
            ]
        )
        == 0
    )
    inspection = json.loads(capsys.readouterr().out)
    # The packaged fixtures are five shapes of ONE policy id, so they are one
    # policy read five times: one row, and the duplicate is reported.
    assert len(inspection["rows"]) == 1
    assert inspection["rows"][0]["in_force"] in ("enforced", "report-only")
    assert len(inspection["duplicates"]) == 1
    assert inspection["policies"]["read_refused"] is True


def _listed(name, group_id=None):
    document = _site(name, None)
    document["facts"] = {
        "site": {
            "group_id": {
                "state": "observed",
                "value": group_id or "00000000-0000-0000-0000-000000000000",
            }
        }
    }
    return document


def _m365_group(identifier, user_owners=None, state="observed"):
    fact = (
        {"state": "observed", "value": user_owners}
        if state == "observed"
        else {"state": state, "detail": "refused"}
    )
    return {
        "resource": {"workload": "entra", "type": "group", "native_id": identifier},
        "provenance": {"collected_at": "2026-11-12T10:00:00Z"},
        "coverage": {"completed": ["groups"], "unavailable": {}},
        "facts": {"group": {"user_owners": fact}},
    }


def test_a_groups_owners_are_shown_beside_a_sites_and_never_counted_as_them():
    """THE COUNTER-CHECK. The site names one administrator and a group; its
    Microsoft 365 group has three owners. Adding them would call the site
    sufficient, and a group owner is not a site collection administrator."""
    inspection = scenarios.ownership(
        [
            _owned("team", named=1, groups=1),
            _listed("team", "AAAA-1"),
            _m365_group("aaaa-1", 3),
        ]
    )
    row = _row(inspection, "team")
    # The site's group administrator is `g0`, which is not the owners claim of
    # the connected group, so nothing is expanded and nothing is added.
    assert row["standing"] == "not-established"
    assert row["administrators_at_least"] == ""
    assert row["connected_group"] == "connected" and row["group_user_owners"] == 3
    assert inspection["sources"]["documents"] == 2


def test_every_way_the_group_join_can_come_up_empty_says_which():
    inspection = scenarios.ownership(
        [
            _owned("plain", named=2),
            _listed("plain"),
            _owned("unread", named=2),
            _listed("unread", "g-unread"),
            _owned("refused", named=2),
            _listed("refused", "g-refused"),
            _m365_group("g-refused", state="permission-denied"),
            _owned("unlisted", named=2),
        ]
    )
    shown = {
        r["name"]: (r["connected_group"], r["group_user_owners"])
        for r in inspection["rows"]
    }
    assert shown == {
        "Plain": ("none", ""),
        "Unread": ("connected", "[not-collected]"),
        "Refused": ("connected", "[permission-denied]"),
        "Unlisted": ("[not-collected]", ""),
    }
    assert "owners that are users [permission-denied]" in scenarios.as_text(inspection)


def test_the_limits_agree_with_what_was_expanded_and_a_refused_site_is_not_answered():
    plain = scenarios.ownership([_owned("a", named=1, groups=1)])
    assert any("no group was expanded" in i for i in plain["not_established"])
    expanded = scenarios.ownership(
        _group_site("s", named=1, claims=[OWNERS_CLAIM], group_owners=3)
    )
    said = " ".join(expanded["not_established"])
    assert "no group was expanded" not in said and "as a range" in said
    documents = _group_site("s", named=0, claims=[OWNERS_CLAIM], group_owners=4)
    documents[0] = _owned("s", state="permission-denied")
    text = scenarios.as_text(scenarios.ownership(documents))
    assert "the group's, not this site's answer" in text


# --- comparing two inspections ---------------------------------------------------


def test_what_entered_left_and_changed_is_reported_row_by_row():
    before = scenarios.external_access(
        [
            _tenant("ExternalUserAndGuestSharing"),
            _site("stays", "Disabled"),
            _site("opens", "Disabled"),
            _site("goes", "Disabled"),
        ]
    )
    after = scenarios.external_access(
        [
            _tenant("ExternalUserAndGuestSharing"),
            _site("stays", "Disabled"),
            _site("opens", "ExternalUserSharingOnly", at="2026-11-12T10:00:00Z"),
            _site("comes", "Disabled"),
        ]
    )
    result = scenarios.difference(before, after)
    assert [r["name"] for r in result["entered"]] == ["Comes"]
    assert [r["name"] for r in result["left"]] == ["Goes"]
    assert result["unchanged"] == 1
    (opened,) = result["changed"]
    assert opened["name"] == "Opens"
    assert opened["changed"]["external_sharing"] == {
        "before": "not-permitted",
        "after": "permitted",
    }
    assert "because" not in opened["changed"]
    text = scenarios.difference_as_text(result)
    assert "external_sharing: not-permitted -> permitted" in text
    assert "deleted" not in text.lower().replace("not the same as", "")


def test_a_question_that_moved_is_not_a_tenant_that_changed():
    """THE COUNTER-CHECK. The same evidence under two thresholds differs in
    every row for a reason that is not in the tenant."""
    documents = [_owned("a", named=2)]
    two = scenarios.ownership(documents, minimum_owners=2)
    three = scenarios.ownership(documents, minimum_owners=3)
    with pytest.raises(scenarios.NotComparable, match="parameters"):
        scenarios.difference(two, three)
    with pytest.raises(scenarios.NotComparable, match="scenario"):
        scenarios.difference(two, scenarios.external_access([_site("a", "Disabled")]))


def test_the_same_evidence_twice_has_nothing_to_report_and_says_why():
    inspection = scenarios.ownership([_owned("a", named=2)])
    result = scenarios.difference(inspection, inspection)
    assert result["same_evidence"] is True
    assert (result["entered"], result["left"], result["changed"]) == ([], [], [])
    assert "same evidence" in scenarios.difference_as_text(result)


def test_the_comparison_command_reads_two_files_and_refuses_what_is_not_one(
    tmp_path, capsys
):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text(json.dumps(scenarios.ownership([_owned("a", named=1)])))
    second.write_text(json.dumps(scenarios.ownership([_owned("a", named=2)])))
    assert main(["governance", "inspect-diff", str(first), str(second)]) == 0
    assert "standing: fewer -> meets" in capsys.readouterr().out
    other = tmp_path / "c.json"
    other.write_text(json.dumps(scenarios.ownership([_owned("a", named=2)], 3)))
    assert main(["inspect-diff", str(first), str(other)]) == 2
    assert "refusing to compare" in capsys.readouterr().err
    junk = tmp_path / "d.json"
    junk.write_text("{}")
    assert main(["inspect-diff", str(first), str(junk)]) == 2


GROUP = "11111111-2222-4333-8444-555555555555"


def _group_site(name, *, named, claims, group_owners):
    owned = _owned(name, named=named, groups=len(claims))
    owned["facts"]["owners"]["groups"] = [{"principal_id": c} for c in claims]
    return [owned, _listed(name, GROUP.upper()), _m365_group(GROUP, group_owners)]


OWNERS_CLAIM = f"c:0o.c|federateddirectoryclaimprovider|{GROUP}_o"
MEMBERS_CLAIM = f"c:0o.c|federateddirectoryclaimprovider|{GROUP}"


def test_the_owners_claim_of_the_connected_group_is_expanded_into_a_range():
    def standing(named, group_owners, minimum=2):
        documents = _group_site(
            "s", named=named, claims=[OWNERS_CLAIM], group_owners=group_owners
        )
        row = _row(scenarios.ownership(documents, minimum_owners=minimum), "s")
        return (
            row["standing"],
            row["administrators_at_least"],
            row["administrators_at_most"],
        )

    assert standing(0, 3) == ("meets", 3, 3)
    assert standing(1, 3) == ("at-least", 3, 4)
    assert standing(0, 1) == ("fewer", 1, 1)
    # One named and one owner may be one person or two: nothing read says.
    assert standing(1, 1) == ("not-established", 1, 2)
    assert standing(0, 0) == ("fewer", 0, 0)


def test_a_range_is_never_a_sum():
    """THE COUNTER-CHECK. Adding the two lists would report three people for
    a site whose one named administrator is also one of its two group owners."""
    inspection = scenarios.ownership(
        _group_site("s", named=1, claims=[OWNERS_CLAIM], group_owners=2), 3
    )
    row = _row(inspection, "s")
    assert (row["administrators_at_least"], row["administrators_at_most"]) == (2, 3)
    assert row["standing"] == "not-established"
    assert "same people" in row["because"]


def test_nothing_but_the_owners_claim_of_that_one_group_is_expanded():
    other = "99999999-2222-4333-8444-555555555555"
    for claims in (
        [MEMBERS_CLAIM],
        [f"c:0o.c|federateddirectoryclaimprovider|{other}_o"],
        [OWNERS_CLAIM, "c:0t.c|tenant|some-security-group"],
        ["Everyone except external users"],
    ):
        inspection = scenarios.ownership(
            _group_site("s", named=1, claims=claims, group_owners=5)
        )
        row = _row(inspection, "s")
        assert row["administrators_at_least"] == "", claims
        assert row["standing"] == "not-established", claims


def test_group_owners_that_were_refused_expand_nothing():
    documents = _group_site("s", named=1, claims=[OWNERS_CLAIM], group_owners=0)
    documents[2] = _m365_group(GROUP, state="permission-denied")
    row = _row(scenarios.ownership(documents), "s")
    assert row["administrators_at_least"] == ""
    assert row["standing"] == "not-established"


# --- which guests a site has met ---------------------------------------------------


def _met(name, ids=(), *, without=0, state="observed"):
    document = _site(name, None)
    if state == "observed":
        facts = {
            "guests": {"state": "observed", "value": len(ids) + without},
            "guest_object_ids": {"state": "observed", "value": list(ids)},
        }
    else:
        facts = {"guests": {"state": state, "detail": "refused"}}
    document["facts"] = {"site_guests": facts}
    return document


def _gid(number):
    return f"00000000-0000-4000-8000-{number:012d}"


def test_a_site_and_a_guest_are_joined_on_the_object_id_and_called_met():
    inspection = scenarios.external_access(
        [
            _site("a", "ExternalUserSharingOnly"),
            _met("a", [_gid(1).upper(), _gid(9)], without=1),
            _site("b", "ExternalUserSharingOnly"),
            _met("b", [_gid(1)]),
            _guest_tenant(2),
            _guest(1),
            _guest(2),
        ]
    )
    assert _row(inspection, "a")["guests_met"] == 3
    assert _row(inspection, "b")["guests_met"] == 1
    assert inspection["guests"]["met_by_sites"] == {
        "distinct_guest_accounts": 2,
        "also_listed_as_guests": 1,
        "not_listed_as_guests": 1,
        "listed_and_met_by_no_site": 1,
    }
    said = " ".join(inspection["not_established"])
    assert "removed from the directory" in said and "type is not Guest" in said
    assert "can open which site today" in said
    assert any("HAS MET" in relation for relation in inspection["relations"])
    assert "is not that account having access" in scenarios.as_text(inspection)


def test_a_site_that_refused_its_list_is_not_a_site_that_met_nobody():
    """THE COUNTER-CHECK. A refused list and an empty list would both show no
    guest; only one of them was observed."""
    inspection = scenarios.external_access(
        [
            _site("refused", "ExternalUserSharingOnly"),
            _met("refused", state="permission-denied"),
            _site("empty", "ExternalUserSharingOnly"),
            _met("empty"),
            _site("unread", "ExternalUserSharingOnly"),
        ]
    )
    assert _row(inspection, "refused")["guests_met"] == "[permission-denied]"
    assert _row(inspection, "empty")["guests_met"] == 0
    assert _row(inspection, "unread")["guests_met"] == "[not-collected]"


def test_without_the_directory_the_two_sides_are_not_compared():
    inspection = scenarios.external_access(
        [_site("a", "Disabled"), _met("a", [_gid(1)])]
    )
    met = inspection["guests"]["met_by_sites"]
    assert met["distinct_guest_accounts"] == 1
    assert met["also_listed_as_guests"] is None
    assert met["not_listed_as_guests"] is None


def _sp(number, *, app=None, enabled=True, own=True, enabled_state="observed"):
    return {
        "resource": {
            "workload": "entra",
            "type": "service-principal",
            "native_id": f"sp-{number}",
        },
        "provenance": {"collected_at": "2026-11-12T10:00:00Z"},
        "coverage": {"completed": ["service_principals"], "unavailable": {}},
        "facts": {
            "service_principal": {
                "app_id": {"state": "observed", "value": app or f"CLIENT-{number}"},
                "account_enabled": (
                    {"state": "observed", "value": enabled}
                    if enabled_state == "observed"
                    else {"state": enabled_state, "detail": "not returned"}
                ),
                "owned_by_this_directory": (
                    {"state": "observed", "value": own}
                    if own is not None
                    else {"state": "missing", "detail": "not known"}
                ),
            }
        },
    }


def test_a_registration_is_joined_to_its_service_principal_on_the_app_id():
    inspection = scenarios.app_exposure(
        [
            _registered(1, []),
            _sp(1),
            _registered(2, []),
            _sp(2, enabled=False),
            _registered(3, []),
            _registered(4, []),
            _sp(4, enabled_state="missing"),
            _sp(7, own=False),
            _sp(8, own=False),
            _sp(9, own=None),
        ]
    )
    shown = {r["native_id"]: r["can_sign_in_here"] for r in inspection["rows"]}
    assert shown == {
        "app-1": "yes",
        "app-2": "no: its service principal is disabled",
        "app-3": "no: no service principal in this directory",
        "app-4": "[missing]",
    }
    assert inspection["service_principals"] == {
        "in_the_evidence": 6,
        "with_a_registration_here": 3,
        "without_a_registration_here": {
            "of_this_directory": 0,
            "of_another_organisation": 2,
            "not_established": 1,
        },
    }
    assert inspection["sources"]["documents"] == 10


def test_without_service_principals_nothing_is_said_about_signing_in():
    """THE COUNTER-CHECK. No service principal collected is not no service
    principal existing: every registration would otherwise read as unable to
    sign in."""
    inspection = scenarios.app_exposure([_registered(1, [])])
    assert _exposed(inspection, 1)["can_sign_in_here"] == "[not-collected]"
    assert inspection["service_principals"] == {"state": "not-collected"}
