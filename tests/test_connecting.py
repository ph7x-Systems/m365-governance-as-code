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
from m365_governance.connecting import (
    Connection,
    Reach,
    connect,
    describe,
    document,
)

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

    assert main(["connect", "--client-id", "11111111-2222-3333-4444-555555555555"]) == 2
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
            "11111111-2222-3333-4444-555555555555",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
            "--format",
            "json",
        ]
    )

    reported = json.loads(capsys.readouterr().out)
    assert code == 0
    assert reported["reach"] == "established"
    assert reported["session"]["identity_kind"] == "delegated"
    assert reported["session"]["observed_tenant_id"] is None
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
            "11111111-2222-3333-4444-555555555555",
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


# ---------------------------------------------------------------------------
# it is a document of the contract it declares
# ---------------------------------------------------------------------------


def _valid(doc: dict) -> list[str]:
    from m365_governance import registry
    from m365_governance.resources import packaged

    return registry.SchemaRegistry.load(packaged("schemas")).problems(doc)


@pytest.mark.parametrize(
    "lines,code,cancelled",
    [
        ([_resolved(), _established()], 0, False),
        ([_resolved(), "AADSTS65001: consent"], 1, False),
        ([_resolved(None, detail="no such tenant")], 1, False),
        ([], 127, False),
        ([_resolved(), "  waiting"], 1, True),
    ],
)
def test_every_outcome_is_a_document_of_the_contract(lines, code, cancelled):
    """Including the ones that reached nothing.

    A failure is exactly the case a consumer cannot reconstruct, so a contract
    that only described the successful attempt would leave it to be inferred.
    """
    doc = document(_attempt(engine=_engine(lines, code, cancelled)))

    assert doc["$schema"].endswith("/connection/1.1.0")
    assert _valid(doc) == []


def test_no_session_is_null_rather_than_an_empty_one():
    """An empty session reads as one that established nothing.

    That is a different and much weaker statement than there being no session
    at all, and a consumer would show a signed-in panel with every field blank.
    """
    doc = document(_attempt(engine=_engine([_resolved(), "refused"], 1)))

    assert doc["session"] is None
    assert doc["address"]["resolved_tenant_id"] is not None


def test_the_document_never_carries_the_resolved_id_as_an_observation():
    """The one line the whole contract exists to hold.

    Copying the public resolution into `observed_tenant_id` would make a lookup
    anybody can perform indistinguishable from something this session saw, in
    the single field a reader trusts to mean what was observed.
    """
    doc = document(_attempt(engine=_engine([_resolved(), _established()])))

    assert (
        doc["address"]["resolved_tenant_id"] == "fcea8c52-d8bb-4836-8ef1-a3ab74265d08"
    )
    assert doc["session"]["observed_tenant_id"] is None
    assert doc["address"]["how"] == "public-discovery"


def test_the_document_carries_no_credential():
    smuggled = _established(client_secret="s3cret", certificate="a-thumbprint")

    doc = document(_attempt(engine=_engine([_resolved(), smuggled])))

    assert "s3cret" not in json.dumps(doc)
    assert "a-thumbprint" not in json.dumps(doc)
    assert _valid(doc) == []


# ---------------------------------------------------------------------------
# The application identity, the reason, and the second question


def test_a_certificate_reaches_the_collector():
    """It used to be validated and then dropped.

    `connect` accepted `--certificate-path`, refused every incoherent
    combination of it, and then signed in as a person. The one command whose
    purpose is to prove an application registration can reach a tenant could
    not prove it for the identity an unattended run uses.
    """
    seen: dict = {}

    def run(argv, on_progress):
        seen["argv"] = argv
        return 1, "", "", False

    _attempt(
        certificate_path="./app.pfx",
        tenant_id="contoso.onmicrosoft.com",
        certificate_password_env="M365_TEST_PASSWORD",
        engine=run,
    )

    argv = seen["argv"]
    assert "-CertificatePath" in argv and "./app.pfx" in argv
    assert "-TenantId" in argv and "contoso.onmicrosoft.com" in argv
    assert "-CertificatePasswordEnv" in argv


def test_the_document_records_which_identity_was_asked_for():
    document_ = document(
        _attempt(
            certificate_path="./app.pfx",
            tenant_id="contoso.onmicrosoft.com",
            engine=_engine([], 1),
        )
    )
    assert document_["requested"]["certificate"] is True
    assert document_["requested"]["tenant_id"] == "contoso.onmicrosoft.com"


DIRECTORY_FAILURES = [
    (
        "AADSTS700016: Application with identifier 'x' was not found",
        "application-not-in-directory",
    ),
    ("AADSTS65001: The user or administrator has not consented", "consent-required"),
    ("AADSTS90002: Tenant 'x' not found", "directory-not-found"),
    ("AADSTS53003: Access has been blocked by Conditional Access", "blocked-by-policy"),
    (
        "AADSTS700027: Client assertion contains an invalid signature",
        "certificate-rejected",
    ),
]


@pytest.mark.parametrize("line,expected", DIRECTORY_FAILURES, ids=lambda v: str(v)[:24])
def test_a_directory_failure_carries_a_reason_a_consumer_can_act_on(line, expected):
    """The vocabulary exists so that nobody has to match on PnP's prose.

    All five of these arrive as `refused`. They send a person to five different
    places, and a consumer that could only read `reach` had to find the
    difference by matching whatever PnP.PowerShell happened to print.
    """
    attempt = _attempt(engine=_engine([_resolved(), line], 1))

    assert attempt.reach is Reach.REFUSED
    assert document(attempt)["reason"] == expected


def test_an_unrecognised_failure_says_so_rather_than_guessing():
    """`not-classified` is an answer. The collector's own words survive it."""
    attempt = _attempt(engine=_engine([_resolved(), "something new happened"], 1))

    assert document(attempt)["reason"] == "not-classified"
    assert "something new happened" in attempt.because


def test_an_address_nothing_owns_is_not_a_consent_problem():
    attempt = _attempt(engine=_engine([_resolved(tenant_id=None), "no"], 1))

    assert document(attempt)["reason"] == "address-not-resolved"


def test_a_session_that_established_carries_established_as_its_reason():
    attempt = _attempt(engine=_engine([_resolved(), _established()]))

    assert document(attempt)["reason"] == "established"


def test_signing_in_is_not_being_authorised():
    """A session opens with zero permissions granted.

    The two answers are separate fields because a product that reported the
    first as the second would be answering a question nobody asked with the
    word a reader takes for the answer to the one they did.
    """
    denied = json.dumps(
        {"state": "denied", "detail": "Access denied.", "read": None},
        separators=(",", ":"),
    )
    attempt = _attempt(
        engine=_engine([_resolved(), "AUTHORIZATION " + denied, _established()])
    )

    assert attempt.reach is Reach.ESTABLISHED
    assert document(attempt)["authorization"]["state"] == "denied"
    assert "denied" in describe(attempt)


def test_authorization_is_always_present_even_where_nothing_was_read():
    """Always emitted. The schema's optionality is for documents, not producers."""
    attempt = _attempt(engine=_engine([_resolved(), _established()]))

    assert document(attempt)["authorization"]["state"] == "not-attempted"


def test_terminal_colour_never_reaches_the_document():
    """Observed on a live refusal, 2026-08-20.

    PnP.PowerShell writes colour into its error stream, and the escape
    sequences travelled into `because` — a field a consumer displays. The words
    are the evidence; the colour is formatting for somebody else's screen.
    """
    coloured = "\x1b[31;1mno active subscriptions for the tenant\x1b[0m"
    attempt = _attempt(engine=_engine([_resolved(), coloured], 1))

    assert "\x1b" not in "".join(attempt.because)
    assert "no active subscriptions for the tenant" in attempt.because


def test_the_engines_own_protocol_is_not_printed_to_a_person():
    """`RESOLVED {...}` is this engine talking to itself.

    Observed on a live refusal, 2026-08-20: the marker lines and another
    product's colour codes were printed straight to the terminal, above the
    summary written for a reader.
    """
    from m365_governance.connecting import readable

    assert readable(_resolved()) is None
    assert readable("CONNECTION {}") is None
    assert readable("AUTHORIZATION {}") is None
    assert readable("\x1b[31;1mConnect-PnPOnline: failed\x1b[0m") == (
        "Connect-PnPOnline: failed"
    )
    assert readable("   ") is None


def test_because_carries_the_reason_rather_than_the_trace_id():
    """Observed on a live refusal, 2026-08-20.

    A directory failure ends with a trace id, a correlation id and a timestamp.
    Taking the last three lines returned exactly those, and left the sentence
    that named the problem out of the document.
    """
    lines = [
        _resolved(tenant_id=None),
        "AADSTS90002: Tenant 'nope' not found. Check to make sure you have the",
        "correct tenant ID and are signing into the correct cloud.",
        "Trace ID: 43081c66-103f-437e-870e-a953e0930300",
        "Correlation ID: b8946607-95fb-4d10-ad29-f08bed0f51ce",
        "Timestamp: 2026-08-20 16:28:09Z",
    ]
    attempt = _attempt(engine=_engine(lines, 1))

    said = "\n".join(attempt.because)
    assert "AADSTS90002" in said
    assert "Correlation ID" not in said
