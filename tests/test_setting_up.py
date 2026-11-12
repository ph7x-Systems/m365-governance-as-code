"""`setup` does the setting up (D90), and its registration is the one write.

Every PowerShell call is stubbed: these tests never install anything, never
open a browser and never reach a tenant.
"""

from __future__ import annotations

import subprocess

import pytest

from m365_governance import setting_up
from m365_governance.cli import main

GUID = "6806fc2a-0000-4000-8000-000000000001"


class Shell:
    """A stand-in for every process `setting_up` starts, recording each one."""

    def __init__(self, replies=None):
        self.calls: list[list[str]] = []
        self.replies = replies or {}

    def __call__(self, command, *, capture=False, timeout=1800):
        self.calls.append(command)
        text = " ".join(command)
        for needle, (code, out) in self.replies.items():
            if needle in text:
                return subprocess.CompletedProcess(command, code, out, "")
        return subprocess.CompletedProcess(command, 0, "", "")


def test_registration_is_refused_without_agreement():
    with pytest.raises(setting_up.RegistrationFailed) as refused:
        setting_up.register("pwsh", "contoso.onmicrosoft.com", agreed=False)
    assert "not agreed" in str(refused.value)


def test_registration_asks_for_the_least_permissions_and_returns_the_id(monkeypatch):
    shell = Shell(
        {"Register-PnPEntraIDAppForInteractiveLogin": (0, f"CLIENT_ID={GUID}\n")}
    )
    monkeypatch.setattr(setting_up, "_run", shell)

    assert setting_up.register("pwsh", "contoso.onmicrosoft.com", agreed=True) == GUID
    command = " ".join(shell.calls[-1])
    assert "-SharePointDelegatePermissions AllSites.FullControl" in command
    assert "-GraphDelegatePermissions User.Read" in command
    assert "ReadWrite" not in command


@pytest.mark.parametrize(
    "output, kind",
    [
        ("Application 'M365 Governance' already exists", "exists"),
        ("Insufficient privileges to complete the operation.", "not-administrator"),
        ("something else went wrong", "failed"),
    ],
)
def test_a_failed_registration_says_what_to_do_next(monkeypatch, output, kind):
    monkeypatch.setattr(setting_up, "_run", Shell({"Register-PnP": (1, output)}))
    with pytest.raises(setting_up.RegistrationFailed) as failed:
        setting_up.register("pwsh", "contoso.onmicrosoft.com", agreed=True)
    assert failed.value.kind == kind


def test_an_address_becomes_the_admin_centre_and_the_root_site():
    expected = (
        "https://contoso-admin.sharepoint.com",
        "https://contoso.sharepoint.com",
    )
    for answer in (
        "contoso",
        "https://contoso.sharepoint.com",
        "https://contoso-admin.sharepoint.com/",
        "https://contoso.sharepoint.com/sites/finance",
    ):
        assert setting_up.target_from(answer) == expected
    assert setting_up.target_from("not an address!") is None
    assert (
        setting_up.tenant_domain("https://contoso-admin.sharepoint.com", None)
        == "contoso.onmicrosoft.com"
    )


def test_pnp_is_installed_for_the_user_when_the_person_agrees(monkeypatch):
    state = {"installed": ""}

    def shell(command, *, capture=False, timeout=1800):
        text = " ".join(command)
        if "Get-Module -ListAvailable PnP.PowerShell" in text:
            return subprocess.CompletedProcess(command, 0, state["installed"], "")
        if "Find-Module PnP.PowerShell" in text:
            return subprocess.CompletedProcess(command, 0, "3.4.1", "")
        if "Install-Module PnP.PowerShell" in text:
            assert "-Scope CurrentUser" in text
            state["installed"] = "3.4.1"
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(setting_up, "_run", shell)
    asker = setting_up.Asker(interactive=False, install=True)
    assert setting_up.ensure_pnp("pwsh", asker, print)
    assert state["installed"] == "3.4.1"


def test_nothing_is_installed_or_registered_without_a_terminal_or_a_flag(monkeypatch):
    asker = setting_up.Asker(interactive=False)
    assert not asker.agree("Install?")
    assert asker.ask("Address?") == ""


def _guided(monkeypatch, tmp_path, answers, shell):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(setting_up, "interactive", lambda: True)
    monkeypatch.setattr(setting_up, "ensure_powershell", lambda asker, say: "pwsh")
    monkeypatch.setattr(setting_up, "ensure_pnp", lambda pwsh, asker, say: True)
    monkeypatch.setattr(setting_up, "_run", shell)
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies))


def test_an_administrator_is_set_up_from_an_address_alone(
    monkeypatch, tmp_path, capsys
):
    shell = Shell(
        {"Register-PnPEntraIDAppForInteractiveLogin": (0, f"CLIENT_ID={GUID}")}
    )
    # the address, option 1, yes to registering, no to connecting now
    _guided(monkeypatch, tmp_path, ["contoso", "1", "y", "n"], shell)

    assert main(["setup"]) == 0
    written = (tmp_path / "m365-governance.toml").read_text(encoding="utf-8")
    assert GUID in written and "https://contoso-admin.sharepoint.com" in written


def test_a_person_who_is_not_an_administrator_gets_the_request_to_send(
    monkeypatch, tmp_path, capsys
):
    _guided(monkeypatch, tmp_path, ["contoso", "3"], Shell())

    assert main(["setup"]) == 0
    request = (tmp_path / "m365-governance-admin-request.txt").read_text(
        encoding="utf-8"
    )
    assert "contoso.onmicrosoft.com" in request and "AllSites.FullControl" in request
    assert not (tmp_path / "m365-governance.toml").exists()


def test_an_administrator_who_lacks_the_right_gets_the_request_instead(
    monkeypatch, tmp_path, capsys
):
    shell = Shell(
        {"Register-PnP": (1, "Insufficient privileges to complete the operation.")}
    )
    _guided(monkeypatch, tmp_path, ["contoso", "1", "y"], shell)

    assert main(["setup"]) == 0
    assert (tmp_path / "m365-governance-admin-request.txt").exists()


def _which(present):
    return lambda name: present.get(name)


def test_powershell_is_installed_when_missing_and_agreed(monkeypatch):
    present = {"brew": "/opt/homebrew/bin/brew"}
    calls = []

    def shell(command, *, capture=False, timeout=1800):
        calls.append(command)
        if command[:2] == ["brew", "install"]:
            present["pwsh"] = "/opt/homebrew/bin/pwsh"
        return subprocess.CompletedProcess(command, 0, "7.6.9", "")

    monkeypatch.setattr(setting_up.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setting_up.shutil, "which", _which(present))
    monkeypatch.setattr(setting_up, "_run", shell)
    monkeypatch.setattr(setting_up, "_latest_powershell", lambda: "7.6.9")

    asker = setting_up.Asker(interactive=False, install=True)
    assert setting_up.ensure_powershell(asker, print) == "/opt/homebrew/bin/pwsh"
    assert ["brew", "install", "--cask", "powershell"] in calls


def test_an_older_powershell_is_updated_through_the_package_that_holds_it(monkeypatch):
    present = {"pwsh": "/opt/homebrew/bin/pwsh", "brew": "/opt/homebrew/bin/brew"}
    calls = []

    def shell(command, *, capture=False, timeout=1800):
        calls.append(command)
        if command[:3] == ["brew", "list", "--versions"]:
            return subprocess.CompletedProcess(command, 0, "powershell 7.6.7_1", "")
        return subprocess.CompletedProcess(command, 0, "7.6.7", "")

    monkeypatch.setattr(setting_up.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setting_up.shutil, "which", _which(present))
    monkeypatch.setattr(setting_up, "_run", shell)
    monkeypatch.setattr(setting_up, "_latest_powershell", lambda: "7.6.9")

    asker = setting_up.Asker(interactive=False, install=True)
    assert setting_up.ensure_powershell(asker, print) == "/opt/homebrew/bin/pwsh"
    assert ["brew", "upgrade", "powershell"] in calls


def test_without_an_installer_it_says_where_to_get_powershell(monkeypatch):
    said = []
    monkeypatch.setattr(setting_up.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setting_up.shutil, "which", _which({}))

    asker = setting_up.Asker(interactive=False, install=True)
    assert setting_up.ensure_powershell(asker, said.append) is None
    assert setting_up.POWERSHELL_DOCS in said[-1]


def test_the_latest_powershell_is_read_from_the_release_tag(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def geturl(self):
            return "https://github.com/PowerShell/PowerShell/releases/tag/v7.6.9"

    monkeypatch.setattr(
        setting_up.urllib.request, "urlopen", lambda *a, **k: Response()
    )
    assert setting_up._latest_powershell() == "7.6.9"

    def offline(*a, **k):
        raise OSError("offline")

    monkeypatch.setattr(setting_up.urllib.request, "urlopen", offline)
    assert setting_up._latest_powershell() is None


def test_a_person_is_asked_and_the_default_holds(monkeypatch):
    replies = iter(["", "n", "contoso"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies))
    asker = setting_up.Asker(interactive=True)
    assert asker.agree("Install?") is True
    assert asker.agree("Register?") is False
    assert asker.ask("Address? ") == "contoso"
    assert setting_up.interactive() is False


def test_an_existing_registration_is_taken_by_its_id(monkeypatch, tmp_path, capsys):
    _guided(monkeypatch, tmp_path, ["contoso", "2", GUID, "n"], Shell())
    assert main(["setup"]) == 0
    assert GUID in (tmp_path / "m365-governance.toml").read_text(encoding="utf-8")


def test_an_id_that_is_not_one_is_refused(monkeypatch, tmp_path, capsys):
    _guided(monkeypatch, tmp_path, ["contoso", "2", "not-an-id"], Shell())
    assert main(["setup"]) == 2
    assert "is not an application id" in capsys.readouterr().err


def test_a_name_already_taken_points_to_its_id(monkeypatch, tmp_path, capsys):
    shell = Shell({"Register-PnP": (1, "Application 'M365 Governance' already exists")})
    _guided(monkeypatch, tmp_path, ["contoso", "1", "y"], shell)
    assert main(["setup"]) == 2
    assert "--client-id" in capsys.readouterr().err


def test_a_registration_that_fails_otherwise_exits_one(monkeypatch, tmp_path, capsys):
    shell = Shell({"Register-PnP": (1, "the network went away")})
    _guided(monkeypatch, tmp_path, ["contoso", "1", "y"], shell)
    assert main(["setup"]) == 1


def test_without_an_address_nothing_can_be_obtained(monkeypatch, tmp_path, capsys):
    _guided(monkeypatch, tmp_path, ["not an address!"], Shell())
    assert main(["setup"]) == 2
    err = capsys.readouterr().err
    assert "is not a SharePoint address" in err and "--tenant-url" in err


def test_registering_needs_powershell_first(monkeypatch, tmp_path, capsys):
    _guided(monkeypatch, tmp_path, ["contoso", "1"], Shell())
    monkeypatch.setattr(setting_up, "ensure_powershell", lambda asker, say: None)
    assert main(["setup"]) == 2
    assert "not ready yet" in capsys.readouterr().err


def test_setup_offers_connect_once_the_file_is_written(monkeypatch, tmp_path, capsys):
    from m365_governance import cli

    reached = []
    monkeypatch.setattr(cli, "main", lambda argv: reached.append(argv) or 0)
    _guided(monkeypatch, tmp_path, ["contoso", "2", GUID, "y"], Shell())
    assert cli._cmd_setup(cli._build_parser().parse_args(["setup"])) == 0
    assert reached and reached[0][0] == "connect"
