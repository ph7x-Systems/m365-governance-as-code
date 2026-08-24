"""The application registration this engine holds, and never spent.

THE DEFECT THESE TESTS EXIST FOR. Every PowerShell collector authenticated as
an application with a certificate. The command line accepted `--client-id`,
`--tenant-id` and `--certificate-path`, and `_authentication` refused an
ambiguous combination of them. The Graph slices then ignored all of it and
required a bearer token pasted into an environment variable by a person.

It survived because it could not be tested. The token arrived from outside, so
there was no code between the command line and the request to exercise, and
nothing failed when the two halves of the engine authenticated as different
things. That is why the acquisition takes its runner as a parameter: every
branch below reaches no directory.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from m365_governance import graph_token

APPLICATION = graph_token.Application(
    client_id="7c9f2a41-3b6d-4e58-9a02-cf51d8e7b3aa",
    tenant_id="c0ffee00-0000-4000-8000-000000000001",
    certificate_path="/somewhere/collector.pfx",
    tenant_url="https://contoso-admin.sharepoint.com",
)

TOKEN = "header.payload.signature"


def _answers(stdout="", stderr="", returncode=0, record=None):
    def run(argv):
        if record is not None:
            record.extend(argv)
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return run


def test_an_incomplete_registration_is_refused_before_anything_runs():
    """The cheapest place to stop is before the process, let alone the network.

    A caller that supplied two of the three things needed gets a sentence
    naming all three, rather than a PowerShell error about a parameter.
    """
    reached = []
    incomplete = graph_token.Application(
        client_id="", tenant_id="t", certificate_path="p", tenant_url="u"
    )

    with pytest.raises(graph_token.Unavailable) as refusal:
        graph_token.acquire(incomplete, run=_answers(record=reached))

    assert "client id" in str(refusal.value)
    assert reached == [], "nothing may run for a registration that is not complete"


def test_the_certificate_password_travels_as_a_name_and_never_as_a_value():
    """THE PROPERTY WORTH A TEST OF ITS OWN.

    A credential in `argv` is in the process list for every account on this
    machine and in the shell history afterwards. The child reads the variable
    itself, so what crosses is the NAME.
    """
    argv = []
    with_password = graph_token.Application(
        client_id=APPLICATION.client_id,
        tenant_id=APPLICATION.tenant_id,
        certificate_path=APPLICATION.certificate_path,
        tenant_url=APPLICATION.tenant_url,
        certificate_password_env="PH7X_CERT_PASSWORD",
    )

    import os

    # A distinctive value, actually present in this process's environment, so
    # that finding it in `argv` would prove the leak rather than suggest it.
    os.environ["PH7X_CERT_PASSWORD"] = "correct-horse-battery-staple-8f21"
    try:
        graph_token.acquire(with_password, run=_answers(stdout=TOKEN, record=argv))
    finally:
        del os.environ["PH7X_CERT_PASSWORD"]

    # THE ENVIRONMENT, NOT `argv`, AND THE PROPERTY IS THE SAME ONE. The values
    # travelled as named parameters until a real run showed that `-Command`
    # binds none of them, so they travel in the child's environment now. This
    # asserts what decides it rather than where it used to be written.
    environment = graph_token.environment_for(with_password)
    assert environment["PH7X_GRAPH_PASSWORD_ENV"] == "PH7X_CERT_PASSWORD", (
        "what crosses is the name of the variable, and the child reads it"
    )
    leaked = "correct-horse-battery-staple-8f21"
    assert not any(leaked in part for part in argv), (
        "the password itself reached the process list"
    )
    assert not any(leaked in value for value in environment.values()), (
        "the password itself was handed to the child instead of its name"
    )


def test_the_token_is_the_last_line_and_not_whatever_powershell_printed_first():
    """PowerShell writes warnings to standard output given the chance.

    A module load notice ahead of the token would be spent as a credential by
    a reader that took the first line, and the request would fail with an
    error about the token rather than about the notice.
    """
    noisy = f"WARNING: a module was loaded from an untrusted repository\n{TOKEN}\n"

    assert graph_token.acquire(APPLICATION, run=_answers(stdout=noisy)) == TOKEN


def test_something_that_is_not_a_bearer_token_is_never_sent_to_microsoft():
    """Refusing here costs nothing; sending an unknown string costs a request
    against a real directory and a failure that reads as a permissions
    problem."""
    with pytest.raises(graph_token.Unavailable) as refusal:
        graph_token.acquire(APPLICATION, run=_answers(stdout="Connected!"))

    assert "not a bearer token" in str(refusal.value)
    assert "Nothing" in str(refusal.value)


def test_a_failure_carries_the_childs_own_words():
    """`certificate not found`, `AADSTS700027` and `application not consented`
    are three problems with three answers. A caller told only that
    authentication failed has to guess which one happened."""
    with pytest.raises(graph_token.Unavailable) as refusal:
        graph_token.acquire(
            APPLICATION,
            run=_answers(returncode=1, stderr="AADSTS700027: certificate is invalid"),
        )

    assert "AADSTS700027" in str(refusal.value)


def test_a_failure_message_never_republishes_a_credential():
    """A refusal is printed, logged and pasted into an issue. A message that
    quoted the token it failed with would publish it in the one place somebody
    is most likely to copy from."""
    leaked = "a" * 400 + "." + "b" * 400 + "." + "c" * 400

    with pytest.raises(graph_token.Unavailable) as refusal:
        graph_token.acquire(
            APPLICATION, run=_answers(returncode=1, stderr=f"failed with {leaked}")
        )

    assert leaked not in str(refusal.value)
    assert "removed from this message" in str(refusal.value)


def test_no_powershell_is_a_sentence_and_not_a_traceback():
    def missing(argv):
        raise FileNotFoundError(2, "No such file or directory: 'pwsh'")

    with pytest.raises(graph_token.Unavailable) as refusal:
        graph_token.acquire(APPLICATION, run=missing)

    assert "pwsh is not on this machine" in str(refusal.value)
    assert "one application registration serves both" in str(refusal.value)


def test_a_sign_in_that_never_answers_says_what_that_means():
    """An application with a certificate needs nobody at a keyboard, so a long
    wait is a network or a directory that did not answer -- never somebody who
    has not finished typing."""
    import subprocess

    def slow(argv):
        raise subprocess.TimeoutExpired(cmd="pwsh", timeout=120)

    with pytest.raises(graph_token.Unavailable) as refusal:
        graph_token.acquire(APPLICATION, run=slow)

    assert "nobody at a keyboard" in str(refusal.value)


def test_this_module_never_writes_a_token_anywhere():
    """READ THE SOURCE, BECAUSE THE PROPERTY IS AN ABSENCE.

    A token that is cached is a token that outlives the operation it was
    authorized for. There is no assertion over behaviour that proves a file was
    not written; what proves it is that nothing here can write one.
    """
    source = (
        __import__("pathlib")
        .Path(graph_token.__file__)
        .read_text(encoding="utf-8")
    )

    for forbidden in ("write_text", "open(", "json.dump", "environ["):
        assert forbidden not in source, (
            f"`{forbidden}` appears in graph_token: a token this module keeps "
            "outlives the authorization it was granted under"
        )


# ---------------------------------------------------------------------------
# the command line, which is where the two halves of the engine disagreed
# ---------------------------------------------------------------------------


def test_a_graph_collect_with_a_certificate_never_asks_for_a_token(
    tmp_path, monkeypatch, capsys
):
    """THE WHOLE DEFECT, IN ONE ASSERTION.

    `collect` given the same application registration every PowerShell
    collector uses answered that it needed an environment variable. A person
    with a certificate, a client id and a directory id was told the tool could
    not run, and the tool was holding everything it needed.
    """
    from m365_governance import cli

    certificate = tmp_path / "collector.pfx"
    certificate.write_bytes(b"not a real certificate")
    monkeypatch.delenv("M365_GOVERNANCE_GRAPH_TOKEN", raising=False)

    code = cli.main(
        [
            "collect",
            "tenant-governance",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
            "--client-id",
            APPLICATION.client_id,
            "--tenant-id",
            APPLICATION.tenant_id,
            "--certificate-path",
            str(certificate),
            "--dry-run",
            "--output",
            str(tmp_path / "out"),
        ]
    )

    printed = capsys.readouterr().out
    assert code == 0
    assert "application-only token minted from" in printed
    assert "M365_GOVERNANCE_GRAPH_TOKEN" not in printed, (
        "a caller holding a certificate must not be told to find a token"
    )


def test_a_graph_collect_with_neither_says_both_ways_in(tmp_path, monkeypatch, capsys):
    """A refusal that named only the environment variable left the caller
    unaware that the application registration was the other answer."""
    from m365_governance import cli

    monkeypatch.delenv("M365_GOVERNANCE_GRAPH_TOKEN", raising=False)

    code = cli.main(
        [
            "collect",
            "tenant-governance",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
            "--client-id",
            APPLICATION.client_id,
            "--output",
            str(tmp_path / "out"),
        ]
    )

    refusal = capsys.readouterr().err
    assert code == 2
    assert "M365_GOVERNANCE_GRAPH_TOKEN" in refusal
    assert "--certificate-path" in refusal


def test_a_token_already_held_is_spent_rather_than_a_directory_reached(
    tmp_path, monkeypatch, capsys
):
    """ORDER MATTERS AND IT IS NOT ARBITRARY. A caller holding a token has
    already been authorized for something; minting a second one would open a
    session nobody asked for, to replace one that works."""
    from m365_governance import cli

    certificate = tmp_path / "collector.pfx"
    certificate.write_bytes(b"not a real certificate")
    monkeypatch.setenv("M365_GOVERNANCE_GRAPH_TOKEN", TOKEN)

    cli.main(
        [
            "collect",
            "tenant-governance",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
            "--client-id",
            APPLICATION.client_id,
            "--tenant-id",
            APPLICATION.tenant_id,
            "--certificate-path",
            str(certificate),
            "--dry-run",
            "--output",
            str(tmp_path / "out"),
        ]
    )

    printed = capsys.readouterr().out
    assert "which is set" in printed
    assert "minted from" not in printed
