"""Discovering the collectors: what is listed, and what it may claim."""

import json

from m365_governance import collecting, live_proof
from m365_governance.cli import main


def _listed(capsys):
    assert main(["collector", "list", "--format", "json"]) == 0
    return {c["name"]: c for c in json.loads(capsys.readouterr().out)}


def test_every_collector_is_listed_with_a_command_that_runs_it(capsys):
    listed = _listed(capsys)
    assert set(listed) == set(collecting.SLICES)
    assert listed["hubs"]["command"] == "m365g spo hub list"
    assert listed["guests"]["permissions"] == ["User.Read.All"]
    # A permission nobody established is said to be that, never left empty.
    assert all(c["permissions"] for c in listed.values())


def test_tenant_verified_is_what_the_registry_holds_and_nothing_typed(capsys):
    """THE COUNTER-CHECK. A collector is verified exactly when the proof
    registry derives a positive state for it; no list here says so."""
    listed = _listed(capsys)
    for name, entry in listed.items():
        state = live_proof.established_state(name)
        assert entry["live_validation_state"] == state, name
        assert entry["tenant_verified"] == (state not in ("none", "negative_only"))
    assert listed["forwarding"]["tenant_verified"] is False


def test_removing_the_proof_removes_the_claim_from_the_listing(capsys, monkeypatch):
    kept = live_proof._registry()["records"]
    monkeypatch.setitem(
        live_proof._registry(),
        "records",
        [r for r in kept if r.get("collector") != "hubs"],
    )
    assert _listed(capsys)["hubs"]["tenant_verified"] is False


def test_describe_says_what_the_proof_did_not_cover(capsys):
    assert main(["collector", "describe", "groups"]) == 0
    text = capsys.readouterr().out
    assert "GroupMember.Read.All" in text and "m365g entra group list" in text
    assert "What its proof did not cover:" in text
    assert main(["collector", "describe", "forwarding"]) == 0
    assert "No directory has answered this read." in capsys.readouterr().out
    assert main(["collector", "describe", "nonsense"]) == 2
    assert "is not a collector" in capsys.readouterr().err


def test_the_text_listing_counts_the_two_states_apart_and_adds_nothing(capsys):
    assert main(["collector", "list"]) == 0
    text = capsys.readouterr().out
    assert "read a directory," in text and "did not." in text
    assert "for part of what they cover" in text
    assert "%" not in text and "score" not in text.lower()


def test_the_contract_test_names_its_fixtures_and_keeps_the_tenant_line_apart(
    capsys,
):
    """A pass here is about the shape of the evidence. It must never read as a
    directory having answered."""
    assert main(["collector", "test", "hubs"]) == 0
    text = capsys.readouterr().out
    assert "Fixtures only. No tenant is reached" in text
    assert "[synthetic]" in text and "CONTRACT       2 of 2 fixtures hold" in text
    assert "TENANT         full" in text
    assert "this test did not establish it" in text
    # THE COUNTER-CHECK. A collector no directory has answered passes its
    # contract test all the same, and the two lines say different things.
    assert main(["collector", "test", "forwarding"]) == 0
    text = capsys.readouterr().out
    assert "fixtures hold" in text
    assert "TENANT         none: contract-tested only" in text


def test_every_collector_passes_its_contract_test(capsys):
    for name in collecting.SLICES:
        assert main(["collector", "test", name]) == 0, name
        capsys.readouterr()


def test_a_fixture_that_breaks_its_contract_fails_the_test(capsys, monkeypatch):
    from m365_governance import cli

    monkeypatch.setattr(
        cli,
        "validate_evidence_document",
        lambda document, location: [
            type("P", (), {"location": location, "message": "broken on purpose"})()
        ],
    )
    assert main(["collector", "test", "hubs"]) == 1
    text = capsys.readouterr().out
    assert "broken on purpose" in text and "0 of 2 fixtures hold" in text
