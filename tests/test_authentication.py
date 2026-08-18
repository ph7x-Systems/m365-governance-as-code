"""Two ways to authenticate, and the caller has to have chosen exactly one.

A delegated run sees what one person sees. An application with a certificate
sees what the tenant granted the application. They answer differently, an empty
result means something different in each, and the evidence has to say which
produced it -- so a command line that names both, or half of one, is refused
before anything reaches a tenant.
"""

from __future__ import annotations

import pytest

from m365_governance.cli import AmbiguousIdentity, _authentication


class _Args:
    def __init__(self, **fields):
        self.client_id = "an-app"
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
        client_id="an-app",
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
        client_id="an-app",
        site_url="https://contoso.sharepoint.com/sites/one",
        tenant_url=None,
        device_login=False,
        certificate_path=tmp_path / "app.pfx",
    )
    assert manifest["identity"]["method"] == "certificate"
    assert manifest["identity"]["client_id"] == "an-app"
    # Nothing about the credential itself.
    assert "app.pfx" not in json.dumps(manifest)


def test_no_secret_reaches_the_collector_as_an_argument(tmp_path, monkeypatch):
    """What crosses the process boundary is the NAME of a variable."""
    from m365_governance.collecting import run_slice

    monkeypatch.setenv("M365_TEST_PW", "hunter2")
    outcome = run_slice(
        "owners",
        client_id="an-app",
        output=tmp_path / "out.json",
        site_url="https://contoso.sharepoint.com/sites/one",
        certificate_path=tmp_path / "app.pfx",
        tenant_id="a-tenant",
        certificate_password_env="M365_TEST_PW",
        dry_run=True,
    )
    assert "M365_TEST_PW" in outcome.stdout
    assert "hunter2" not in outcome.stdout
