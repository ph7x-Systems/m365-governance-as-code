"""The delegated Graph token: what is asked for, and what is never done."""

import types

import pytest

from m365_governance import graph_token
from m365_governance.cli import main

TOKEN = "aaa.bbb.ccc"


def _finished(stdout="", stderr="", code=0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)


def _acquire(run, **over):
    settings = {
        "client_id": "c0ffee00-0000-4000-8000-000000000001",
        "tenant_url": "https://contoso-admin.sharepoint.com",
        "scopes": ("User.Read.All",),
        **over,
    }
    return graph_token.acquire_delegated(run=run, **settings)


def test_the_token_is_the_last_line_and_nothing_travels_in_an_argument():
    seen = []

    def run(argv):
        seen.append(argv)
        return _finished(stdout=f"a line of noise\n{TOKEN}\n")

    assert _acquire(run) == TOKEN
    argv = seen[0]
    assert argv[:3] == ["pwsh", "-NoProfile", "-Command"]
    joined = " ".join(argv)
    for value in ("c0ffee00", "contoso", "User.Read.All"):
        assert value not in joined, "an input travelled in the process list"


def test_only_the_scopes_named_are_asked_for():
    script = graph_token.DELEGATED_SCRIPT
    assert "-Scopes $Scopes" in script and "$env:PH7X_GRAPH_SCOPES" in script
    for wider in ("Directory.Read.All", ".default", "ReadWrite", "FullControl"):
        assert wider not in script
    for kept in ("-PersistLogin", "Out-File", "Set-Content", "Export-"):
        assert kept not in script, "the script keeps or writes something"


def test_a_collector_with_no_recorded_scope_gets_no_token():
    for scopes in ((), ("not-established",)):
        with pytest.raises(graph_token.Unavailable, match="no Microsoft Graph scope"):
            _acquire(lambda argv: _finished(stdout=TOKEN), scopes=scopes)


def test_a_sign_in_that_was_not_completed_is_a_refusal_that_names_the_scope():
    with pytest.raises(graph_token.Unavailable) as refusal:
        _acquire(lambda argv: _finished(stderr="AADSTS65004: declined", code=1))
    assert "User.Read.All" in str(refusal.value)
    assert "consent" in str(refusal.value)


def test_a_failure_never_quotes_a_token():
    leaked = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
    with pytest.raises(graph_token.Unavailable) as refusal:
        _acquire(lambda argv: _finished(stderr=f"failed with {leaked}", code=1))
    assert leaked not in str(refusal.value)


def test_something_that_is_not_a_token_is_never_spent():
    with pytest.raises(graph_token.Unavailable, match="not a bearer token"):
        _acquire(lambda argv: _finished(stdout="Welcome to PowerShell\n"))


def test_a_graph_read_without_a_certificate_signs_in_as_the_person(
    monkeypatch, tmp_path, capsys
):
    """The command asks for the collector's own scope and nothing wider, and a
    refusal there stops the run before anything is read."""
    asked = {}

    def delegated(**named):
        asked.update(named)
        raise graph_token.Unavailable("declined at the sign-in")

    monkeypatch.setattr(graph_token, "acquire_delegated", delegated)
    monkeypatch.delenv("M365_GOVERNANCE_GRAPH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "entra",
            "guest",
            "list",
            "--client-id",
            "c0ffee00-0000-4000-8000-000000000001",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
        ]
    )
    assert code == 2
    assert asked["scopes"] == ("User.Read.All",)
    assert "declined at the sign-in" in capsys.readouterr().err
