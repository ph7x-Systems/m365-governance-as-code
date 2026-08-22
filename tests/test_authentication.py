"""Two ways to authenticate, and the caller has to have chosen exactly one.

A delegated run sees what one person sees. An application with a certificate
sees what the tenant granted the application. They answer differently, an empty
result means something different in each, and the evidence has to say which
produced it -- so a command line that names both, or half of one, is refused
before anything reaches a tenant.
"""

from __future__ import annotations

import pytest

from m365_governance.cli import AmbiguousIdentity, _authentication, main


class _Args:
    def __init__(self, **fields):
        self.client_id = "c0ffee00-0000-4000-8000-000000000001"
        self.device_login = False
        self.tenant_id = None
        self.certificate_path = None
        self.certificate_password_env = None
        for name, value in fields.items():
            setattr(self, name, value)


def test_a_delegated_sign_in_needs_nothing_else():
    _authentication(_Args())
    _authentication(_Args(device_login=True))


def test_both_modes_at_once_is_refused(tmp_path):
    pfx = tmp_path / "app.pfx"
    pfx.write_bytes(b"not a real certificate")
    with pytest.raises(AmbiguousIdentity) as caught:
        _authentication(
            _Args(certificate_path=pfx, tenant_id="a-tenant", device_login=True)
        )
    assert "Choose one" in str(caught.value)


def test_a_certificate_without_a_directory_is_refused(tmp_path):
    pfx = tmp_path / "app.pfx"
    pfx.write_bytes(b"not a real certificate")
    with pytest.raises(AmbiguousIdentity) as caught:
        _authentication(_Args(certificate_path=pfx))
    assert "--tenant-id" in str(caught.value)


def test_a_directory_without_a_certificate_is_refused():
    with pytest.raises(AmbiguousIdentity):
        _authentication(_Args(tenant_id="a-tenant"))


def test_a_password_variable_that_is_not_set_is_refused(tmp_path, monkeypatch):
    """The NAME is passed, never the value, so an unset name is a silent
    fallback to no password rather than an error nobody sees."""
    pfx = tmp_path / "app.pfx"
    pfx.write_bytes(b"not a real certificate")
    monkeypatch.delenv("M365_TEST_PW", raising=False)
    with pytest.raises(AmbiguousIdentity) as caught:
        _authentication(
            _Args(
                certificate_path=pfx,
                tenant_id="a-tenant",
                certificate_password_env="M365_TEST_PW",
            )
        )
    assert "empty or unset" in str(caught.value)


def test_a_certificate_that_is_not_there_is_refused(tmp_path):
    with pytest.raises(AmbiguousIdentity) as caught:
        _authentication(
            _Args(certificate_path=tmp_path / "absent.pfx", tenant_id="a-tenant")
        )
    assert "does not exist" in str(caught.value)


def test_the_password_itself_is_not_a_command_line_option():
    """It would be in the shell history and in the process list of every user
    on the machine. The option takes the name of an environment variable."""
    from m365_governance.cli import _build_parser

    for command in ("collect", "connect"):
        options = {
            option
            for action in _build_parser()
            ._subparsers._group_actions[0]  # type: ignore[union-attr]
            .choices[command]
            ._actions
            for option in action.option_strings
        }
        assert "--certificate-password-env" in options
        assert "--certificate-password" not in options


def test_the_certificate_run_is_recorded_as_an_application(tmp_path):
    """The evidence says which identity produced it, and it was hard-coded."""
    import json

    from m365_governance.collecting import Outcome, build_manifest, run_slice

    outcome = run_slice(
        "owners",
        client_id="c0ffee00-0000-4000-8000-000000000001",
        output=tmp_path / "out.json",
        site_url="https://contoso.sharepoint.com/sites/one",
        certificate_path=tmp_path / "app.pfx",
        tenant_id="a-tenant",
        dry_run=True,
    )
    # A dry run returns the command it would have run, and runs nothing.
    assert "-CertificatePath" in outcome.stdout
    assert "-TenantId" in outcome.stdout

    # A dry run has no state to account for, so the manifest is built from a
    # real outcome shape rather than from the dry one.
    ran = Outcome("owners", 0, 0.1, [], "", "")
    manifest = build_manifest(
        ran,
        directory=tmp_path,
        client_id="c0ffee00-0000-4000-8000-000000000001",
        site_url="https://contoso.sharepoint.com/sites/one",
        tenant_url=None,
        device_login=False,
        certificate_path=tmp_path / "app.pfx",
    )
    assert manifest["identity"]["method"] == "certificate"
    assert manifest["identity"]["client_id"] == "c0ffee00-0000-4000-8000-000000000001"
    # Nothing about the credential itself.
    assert "app.pfx" not in json.dumps(manifest)


def test_no_secret_reaches_the_collector_as_an_argument(tmp_path, monkeypatch):
    """What crosses the process boundary is the NAME of a variable."""
    from m365_governance.collecting import run_slice

    monkeypatch.setenv("M365_TEST_PW", "hunter2")
    outcome = run_slice(
        "owners",
        client_id="c0ffee00-0000-4000-8000-000000000001",
        output=tmp_path / "out.json",
        site_url="https://contoso.sharepoint.com/sites/one",
        certificate_path=tmp_path / "app.pfx",
        tenant_id="a-tenant",
        certificate_password_env="M365_TEST_PW",
        dry_run=True,
    )
    assert "M365_TEST_PW" in outcome.stdout
    assert "hunter2" not in outcome.stdout


# ---------------------------------------------------------------------------
# An identifier that cannot be an application registration


MALFORMED = [
    "not-a-guid",
    "",
    "   ",
    "1111",
    "11111111-2222-3333-4444-5555555555",
    "an-app",
]


@pytest.mark.parametrize("value", MALFORMED, ids=lambda v: repr(v))
def test_an_identifier_that_cannot_be_a_registration_is_refused_before_the_network(
    capsys, value
):
    """Exit 2, and no process is started.

    Audited on 2026-08-20 against a live tenant: a value of the wrong shape
    started PowerShell, opened a browser, and failed in the directory with
    `AADSTS700016`. The product's own worst error was diagnosed by Microsoft,
    in a window, outside the terminal a person was looking at.
    """
    code = main(
        [
            "connect",
            "--client-id",
            value,
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
        ]
    )

    assert code == 2
    err = capsys.readouterr().err
    assert "not an application registration" in err
    assert "Traceback" not in err


def test_a_well_formed_identifier_is_not_a_claim_that_it_exists():
    """The shape check removes a class of failure. It proves nothing else."""
    from m365_governance.cli import _application_id

    _application_id("c0ffee00-0000-4000-8000-000000000001")


def test_a_documentation_placeholder_never_reaches_a_directory():
    """FOUND BY THE OWNER MEETING IT TWICE IN ONE EVENING.

    The manual prints a specimen of what `connect` reports, and a specimen
    contains a client id. Somebody copied it, ran it against their own tenant,
    and met `AADSTS700016: Application with identifier
    '11111111-2222-3333-4444-555555555555' was not found in the directory ...`
    — an error naming their directory, which reads as though something is wrong
    with it.

    The GUID is well formed, so shape validation passes it. This is the same
    principle one step further: a failure the directory should never have been
    asked about is refused before a browser opens.
    """
    import pytest

    from m365_governance.cli import AmbiguousIdentity, _application_id

    for placeholder in (
        "11111111-2222-3333-4444-555555555555",
        "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE",
        "00000000-0000-0000-0000-000000000000",
    ):
        with pytest.raises(AmbiguousIdentity) as refusal:
            _application_id(placeholder)
        assert "documentation placeholder" in str(refusal.value)


def test_a_rehearsal_may_use_the_identifier_the_manual_prints():
    """`--dry-run` contacts nothing, and a guard that refused the documented
    example in the one mode where it is safe would make the manual unusable."""
    from m365_governance.cli import _application_id

    _application_id("11111111-2222-3333-4444-555555555555", reaches_a_directory=False)
