"""Reaching a tenant, and saying only what was established.

`doctor` answers whether this installation is sound. Nothing answered the other
half: whether the application registration in front of you can reach the tenant
in front of you, and as whom. It was found out several minutes into a
collection, from a failure that looked like a tenant problem.

Nothing here reaches a tenant. The collector process is stood in for, because
what is under test is the reading: which of four words an attempt earns, and
what the engine is allowed to say afterwards.

THE ONE THING THESE TESTS ARE MOST FOR. Connecting must not claim to know which
organisation answered. A host is an address; the identity is the directory id,
and no collection path for it is proven on a tenant. Several tests below exist
only to hold that line.
"""

from __future__ import annotations

import json

import pytest

from m365_governance import connecting
from m365_governance.connecting import Connection, Reach, connect, describe

SESSION = {
    "connected": True,
    "host": "contoso.sharepoint.com",
    "url": "https://contoso-admin.sharepoint.com",
    "client_id": "11111111-2222-3333-4444-555555555555",
    "identity_kind": "delegated",
    "connection_type": "TenantAdmin",
    "scopes": ["AllSites.FullControl", "User.Read"],
    "observed_tenant_id": None,
}


def _engine(lines: list[str], returncode: int = 0, cancelled: bool = False):
    """A collector that printed these lines and ended this way."""

    def run(argv, on_progress):
        for line in lines:
            if on_progress is not None:
                on_progress(line)
        return returncode, "\n".join(lines), "", cancelled

    return run


def _attempt(**kwargs) -> Connection:
    settings = {
        "client_id": "11111111-2222-3333-4444-555555555555",
        "tenant_url": "https://contoso-admin.sharepoint.com",
    }
    return connect(**{**settings, **kwargs})


def _established(**overrides) -> str:
    return "CONNECTION " + json.dumps({**SESSION, **overrides}, separators=(",", ":"))


def _resolved(tenant_id: str | None = "fcea8c52-d8bb-4836-8ef1-a3ab74265d08", **over):
    body = {
        "host": "contoso.sharepoint.com",
        "resolved_tenant_id": tenant_id,
        "how": "public-discovery",
        "detail": None,
        **over,
    }
    return "RESOLVED " + json.dumps(body, separators=(",", ":"))


# ---------------------------------------------------------------------------
# the four words
# ---------------------------------------------------------------------------


def test_a_session_that_opened_is_established():
    attempt = _attempt(engine=_engine(["  connecting", _established()]))

    assert attempt.reach is Reach.ESTABLISHED
    assert attempt.host == "contoso.sharepoint.com"
    assert attempt.identity == "delegated"


def test_a_tenant_that_answered_and_refused_is_not_a_tenant_that_never_answered():
    """Two different sentences to somebody holding an app registration.

    Collapsing them sends a person to check their network when the answer was
    consent, and to check consent when nothing was listening.
    """
    refused = _attempt(
        engine=_engine(["AADSTS65001: consent has not been granted"], returncode=1)
    )
    unreachable = _attempt(engine=_engine([], returncode=127))

    assert refused.reach is Reach.REFUSED
    assert unreachable.reach is Reach.UNREACHABLE


def test_cancelled_is_the_callers_word_and_never_an_exit_code():
    # A sign-in abandoned at the browser and one killed by the network exit the
    # same way. Only the caller knows which happened.
    attempt = _attempt(engine=_engine(["  waiting"], returncode=1, cancelled=True))

    assert attempt.reach is Reach.CANCELLED


def test_exiting_zero_and_saying_nothing_is_not_a_session():
    """Something answered and this engine did not understand it.

    Reading silence as success would be the whole product's failure mode in one
    line: an absence rendered as a pass.
    """
    attempt = _attempt(engine=_engine(["  something else entirely"], returncode=0))

    assert attempt.reach is Reach.UNREACHABLE


def test_two_session_lines_are_not_one_session():
    # Belt and braces on the stream: a collector that somehow printed twice is
    # a collector this engine does not understand, not a session to trust.
    doubled = _engine([_established(), _established(host="fabrikam.sharepoint.com")])

    assert _attempt(engine=doubled).reach is Reach.UNREACHABLE


def test_a_session_line_that_is_not_json_is_not_a_session():
    attempt = _attempt(engine=_engine(["CONNECTION {truncated"]))

    assert attempt.reach is Reach.UNREACHABLE


# ---------------------------------------------------------------------------
# what it refuses to claim, which is the point
# ---------------------------------------------------------------------------


def test_connecting_never_says_which_organisation_answered():
    """A host is an endpoint. The identity is the directory id.

    No collection path for it is proven on a tenant, so the honest answer after
    a successful sign-in is the address and `not-established`. Anything else is
    inference from a hostname somebody typed.
    """
    attempt = _attempt(engine=_engine([_established()]))

    assert attempt.observed_tenant_id is None
    assert attempt.host == "contoso.sharepoint.com"
    assert any("directory identity was not read" in r for r in attempt.because)


def test_the_report_says_the_session_directory_is_not_established():
    text = describe(_attempt(engine=_engine([_resolved(), _established()])))

    assert "identity   delegated" in text
    assert "observed   not established" in text
    assert "IS NOT ESTABLISHED" in text


def test_a_failed_attempt_reports_not_established_rather_than_nothing():
    attempt = _attempt(engine=_engine(["nope"], returncode=1))

    assert attempt.identity == "not-established"
    assert attempt.host is None


# ---------------------------------------------------------------------------
# it never prints a credential
# ---------------------------------------------------------------------------


def test_a_credential_the_connection_object_carries_is_never_reported():
    """PnP's connection object also exposes ClientSecret and Certificate.

    Neither is read by the collector and neither may ever be: a command that
    printed a credential would put one into a terminal, a log, and whatever
    captured that log. This holds the line from the reading side too.
    """
    smuggled = _established(client_secret="s3cret", certificate="a-thumbprint")

    text = describe(_attempt(engine=_engine([smuggled])))

    assert "s3cret" not in text
    assert "a-thumbprint" not in text


# ---------------------------------------------------------------------------
# a verdict always carries its reasons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lines,code,cancelled",
    [
        ([_established()], 0, False),
        (["AADSTS50011: redirect mismatch"], 1, False),
        ([], 127, False),
        (["  waiting"], 1, True),
    ],
)
def test_every_outcome_says_why(lines, code, cancelled):
    attempt = _attempt(engine=_engine(lines, code, cancelled))

    assert attempt.because
    assert all(reason.strip() for reason in attempt.because)


def test_a_failure_carries_the_collectors_own_last_words():
    attempt = _attempt(
        engine=_engine(["opening", "AADSTS65001: consent has not been granted"], 1)
    )

    assert any("AADSTS65001" in reason for reason in attempt.because)


# ---------------------------------------------------------------------------
# the stream, which a device code depends on
# ---------------------------------------------------------------------------


def test_every_line_reaches_the_caller_as_it_is_printed():
    """A device-code sign-in prints a code somebody reads off the screen.

    A caller that buffered would ask a person to wait for something they had
    already been shown, and the code expires.
    """
    seen: list[str] = []
    _attempt(
        engine=_engine(
            [
                "To sign in, use a web browser to open https://microsoft.com/devicelogin",
                "and enter the code F7GQ4XN9J to authenticate.",
                _established(),
            ],
        ),
        on_progress=seen.append,
    )

    assert "F7GQ4XN9J" in seen[1]
    assert len(seen) == 3


def test_what_was_asked_is_carried_beside_what_was_established():
    attempt = _attempt(
        site_url="https://contoso.sharepoint.com/sites/marketing",
        device_login=True,
        engine=_engine([_established()]),
    )

    assert attempt.requested["device_login"] is True
    assert attempt.requested["site_url"].endswith("/sites/marketing")
    assert attempt.requested["client_id"] == "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# the command
# ---------------------------------------------------------------------------


def test_connect_refuses_without_an_address(capsys):
    from m365_governance.cli import main

    assert main(["connect", "--client-id", "an-id"]) == 2
    assert "an address to reach" in capsys.readouterr().err


def test_connect_reports_json_for_a_consumer(monkeypatch, capsys):
    from m365_governance.cli import main

    monkeypatch.setattr(connecting, "_run", _engine([_established()]))
    monkeypatch.setattr(
        "m365_governance.collecting.preflight", lambda: [], raising=True
    )

    code = main(
        [
            "connect",
            "--client-id",
            "an-id",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
            "--format",
            "json",
        ]
    )

    reported = json.loads(capsys.readouterr().out)
    assert code == 0
    assert reported["reach"] == "established"
    assert reported["identity"] == "delegated"
    assert reported["observed_tenant_id"] is None
    assert reported["session"]
    assert reported["because"]


def test_connect_exits_one_when_it_could_not_reach(monkeypatch, capsys):
    from m365_governance.cli import main

    monkeypatch.setattr(connecting, "_run", _engine(["refused"], returncode=1))
    monkeypatch.setattr(
        "m365_governance.collecting.preflight", lambda: [], raising=True
    )

    code = main(
        [
            "connect",
            "--client-id",
            "an-id",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
        ]
    )

    assert code == 1
    assert "REFUSED" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# two questions, and one field would answer neither
# ---------------------------------------------------------------------------


def test_resolving_an_address_is_not_observing_a_session():
    """The distinction the whole command is shaped around.

    Which directory owns an address is answerable from public discovery, by
    anybody, without a token. Which directory a session operated in is only
    answerable by the session. A GUID the whole world can obtain without
    reaching the tenant is not evidence that a collection looked at it.
    """
    attempt = _attempt(engine=_engine([_resolved(), _established()]))

    assert attempt.resolved_tenant_id == "fcea8c52-d8bb-4836-8ef1-a3ab74265d08"
    assert attempt.observed_tenant_id is None


def test_an_address_resolves_even_when_the_sign_in_fails():
    """Resolution needs no session, so a refusal does not remove the answer.

    A tenant that would not have us still has an address, and somebody
    diagnosing a consent problem is helped by knowing which directory they were
    actually pointed at.
    """
    attempt = _attempt(
        engine=_engine([_resolved(), "AADSTS65001: consent has not been granted"], 1)
    )

    assert attempt.reach is Reach.REFUSED
    assert attempt.resolved_tenant_id == "fcea8c52-d8bb-4836-8ef1-a3ab74265d08"


def test_a_host_that_does_not_exist_says_so_rather_than_resolving_to_nothing():
    attempt = _attempt(
        engine=_engine([_resolved(None, detail="no such tenant"), "gone"], 1)
    )

    assert attempt.resolved_tenant_id is None
    assert "no such tenant" in describe(attempt)


def test_the_report_keeps_the_two_answers_under_separate_headings():
    """A reader who saw one GUID under one heading would conclude the session
    had been observed in that directory. It has not."""
    text = describe(_attempt(engine=_engine([_resolved(), _established()])))

    assert "Address resolution" in text
    assert "Authenticated session" in text
    assert text.index("Address resolution") < text.index("Authenticated session")
    assert "observed   not established" in text
    assert "does not stand in for it" in text
