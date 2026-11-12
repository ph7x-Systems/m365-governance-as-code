"""A session is kept only because somebody logged in, and is used only for its tenant.

docs/CLI.md states the rules; this file is where they fail if broken.

NO TENANT IS REACHED AND NOTHING AUTHENTICATES. The collector process is
replaced, where the suite's own guard says to replace it, by a stand-in that
writes down what it was asked and plays the one behaviour of the sign-in
library these commands rely on, as that library documents it: a delegated
sign-in made with `-PersistLogin` is kept per tenant and application
registration, and a later delegated sign-in for the same pair is silent.
Whether the real library does so against a real tenant is a live observation
and is not claimed here.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from m365_governance import cli, collecting, connecting, sessions

CLIENT = "3f6c1d9a-7b24-4e58-9a01-c2d47be8f615"
OTHER_CLIENT = "a84e02c7-1d3b-49f6-8e25-70b9d1c4f3a2"
TENANT = "https://contoso-admin.sharepoint.com"
SITE = "https://contoso.sharepoint.com/sites/a"
ELSEWHERE = "https://fabrikam-admin.sharepoint.com"


def _tenant(url: str) -> str:
    first, _, rest = (urlparse(url).hostname or "").partition(".")
    for suffix in ("-admin", "-my"):
        if first.endswith(suffix):
            first = first[: -len(suffix)]
    return first + "." + rest


class StandIn:
    """What the engine is given in place of the collector process.

    It writes down what it was asked and plays the sign-in library's documented
    behaviour: a delegated sign-in made with `-PersistLogin` is kept per tenant
    and application registration, a later delegated sign-in for the same pair
    is silent, and the Logout mode removes it. `refuses` makes every call fail
    as an expired sign-in does; `plaintext` makes a kept sign-in land in a
    readable file, as the library's unprotected fallback would.
    """

    def __init__(self) -> None:
        self.asked: list[dict] = []
        self.kept: list[list[str]] = []
        self.refuses = False
        self.plaintext: Path | None = None

    def __call__(self, argv, on_progress=None):
        argv = [str(a) for a in argv[1:]]

        def option(name):
            return argv[argv.index(name) + 1] if name in argv else None

        mode, client = option("-Mode"), option("-ClientId")
        url = option("-TenantUrl") or option("-SiteUrl") or ""
        key = [_tenant(url), (client or "").lower()]
        certificate = "-CertificatePath" in argv
        silent = certificate or key in self.kept
        self.asked.append({"argv": argv, "mode": mode, "interactive": not silent})
        if self.refuses:
            err = "AADSTS700082: The refresh token has expired due to inactivity."
            return 1, "", err, False
        if "-PersistLogin" in argv and not certificate:
            if key not in self.kept:
                self.kept.append(key)
            if self.plaintext:
                self.plaintext.parent.mkdir(parents=True, exist_ok=True)
                self.plaintext.write_text('{"AccessToken": {}, "RefreshToken": {}}')
        lines = []
        host = urlparse(url).hostname
        if mode == "Connect":
            kind = "application" if certificate else "delegated"
            delegated = "device-code" if "-DeviceLogin" in argv else "interactive"
            method = "certificate" if certificate else delegated
            facts = {"host": host, "identity_kind": kind, "identity_method": method}
            lines = [
                "RESOLVED " + json.dumps({"host": host}),
                "AUTHORIZATION " + json.dumps({"read": "allowed"}),
                "CONNECTION " + json.dumps(facts),
            ]
        elif mode == "Logout":
            self.kept = [k for k in self.kept if k != key]
            lines = ["LOGOUT " + json.dumps({"cleared": True, "host": host})]
        return 0, "\n".join(lines), "", False


@pytest.fixture
def machine(tmp_path, monkeypatch, capsys):
    """One user's machine: a home, a record, and a collector that signs nobody in.

    The command line runs in this process, so what it does is measured. The
    collector is replaced where the suite's guard says to replace it
    (`_run`): no process is started and nothing can authenticate.
    """
    (tmp_path / "bin").mkdir()
    present = tmp_path / "bin" / "pwsh"
    present.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    present.chmod(0o755)
    (tmp_path / "home").mkdir()
    (tmp_path / "work").mkdir()
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("M365G_HOME", str(tmp_path / "record"))
    monkeypatch.delenv("PH7X_ENGINE", raising=False)
    monkeypatch.chdir(tmp_path / "work")
    collector = StandIn()
    monkeypatch.setattr(collecting, "_run", collector)
    monkeypatch.setattr(connecting, "_run", collector)

    def run(*argv):
        capsys.readouterr()
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else 1
        said = capsys.readouterr()
        return SimpleNamespace(returncode=code, stdout=said.out, stderr=said.err)

    run.asked = lambda: collector.asked
    run.collector = collector
    run.root = tmp_path
    return run


def _login(run, *more):
    return run("login", "--client-id", CLIENT, "--tenant-url", TENANT, *more)


needs_protected_storage = pytest.mark.skipif(
    not sessions.storage().protected,
    reason="this machine has no protected storage to keep a session in",
)


# --- nothing is kept unless somebody logged in --------------------------------


def test_no_command_but_login_asks_for_a_sign_in_to_be_kept(machine):
    machine("connect", "--client-id", CLIENT, "--tenant-url", TENANT)
    machine(
        "collect",
        "sites",
        "--client-id",
        CLIENT,
        "--tenant-url",
        TENANT,
        "--output",
        "e",
    )
    machine(
        "run",
        "--client-id",
        CLIENT,
        "--tenant-url",
        TENANT,
        "--site-url",
        SITE,
        "--output",
        "e",
    )
    asked = machine.asked()
    assert asked, "the commands did not reach the collector at all"
    assert not [a for a in asked if "-PersistLogin" in a["argv"]]
    assert not (machine.root / "record").exists(), (
        "a record was written without a login"
    )


def test_without_a_login_every_collection_signs_in_for_itself(machine):
    for _ in range(3):
        machine(
            "collect",
            "sites",
            "--client-id",
            CLIENT,
            "--tenant-url",
            TENANT,
            "--output",
            "e",
        )
    assert [a["interactive"] for a in machine.asked()] == [True, True, True]


# --- the gate: sixteen collections, not sixteen sign-ins -----------------------


@needs_protected_storage
def test_every_collection_after_one_login_does_not_ask_again(machine, monkeypatch):
    """One interactive sign-in at login; the collections that follow are silent.

    Every slice the engine has is collected once. The twelve that sign in
    through the SharePoint collector reuse the session. The rest are named
    here with the reason, because a gate that hid them would be claiming a
    session covers what it does not (docs/CLI.md).
    """
    from m365_governance import graph_token

    graph_scopes = []

    def delegated(**named):
        graph_scopes.append(named["scopes"])
        raise graph_token.Unavailable("no directory in a test")

    monkeypatch.setattr(graph_token, "acquire_delegated", delegated)
    assert _login(machine).returncode == 0
    for name, chosen in collecting.SLICES.items():
        argv = ["collect", name, "--output", "e"]
        if chosen.needs_site:
            argv += ["--site-url", SITE]
        machine(*argv)

    asked = machine.asked()
    assert asked[0]["mode"] == "Connect" and asked[0]["interactive"], (
        "login is the one interactive sign-in"
    )
    sharepoint = {
        s.mode
        for s in collecting.SLICES.values()
        if s.source == "powershell" and s.collector.name == "Get-SpoEvidence.ps1"
    }
    collected = [a for a in asked[1:] if a["mode"] in sharepoint]
    assert len(collected) == 16, sorted(a["mode"] for a in collected)
    assert not [a["mode"] for a in collected if a["interactive"]], (
        "a SharePoint collection asked again"
    )
    assert all(CLIENT in a["argv"] for a in collected)
    assert not [a for a in asked[1:] if "-PersistLogin" in a["argv"]], (
        "a collection decided to keep a sign-in"
    )

    # A Graph read asks as the same person, for its own collector's scopes
    # and no others, through the registration the connection holds.
    assert sorted(graph_scopes) == sorted(
        tuple(s.permissions) for s in collecting.SLICES.values() if s.source == "graph"
    )

    # What the SharePoint session itself does not carry, by name.
    uncovered = sorted(
        n
        for n, s in collecting.SLICES.items()
        if s.source != "powershell" or s.collector.name != "Get-SpoEvidence.ps1"
    )
    assert uncovered == [
        "applications",
        "conditional-access",
        "forwarding",
        "groups",
        "guests",
        "licensing",
        "service-principals",
        "tenant-governance",
    ]


@needs_protected_storage
def test_login_reports_authentication_and_authorization_apart(machine):
    out = _login(machine, "--format", "json")
    assert out.returncode == 0, out.stderr
    said = json.loads(out.stdout)
    assert said["logged_in"] is True
    assert (
        said["record"]["persisted"] is True
        and said["record"]["method"] == "interactive"
    )
    assert "access" in json.dumps(said["connection"]) or "authorization" in json.dumps(
        said["connection"]
    )


# --- tokens: never here, never printed, never in plain text --------------------


@needs_protected_storage
def test_the_record_and_every_stream_carry_no_token(machine):
    out = _login(machine)
    status = machine("status", "--format", "json")
    record = (machine.root / "record" / sessions.NAME).read_text()
    for text in (out.stdout, out.stderr, status.stdout, record):
        low = text.lower()
        assert (
            "refresh_token" not in low
            and "access_token" not in low
            and "eyj" not in low
        )
    assert set(json.loads(record)["connections"][0]) & sessions.FORBIDDEN == set()
    if os.name != "nt":
        assert (machine.root / "record" / sessions.NAME).stat().st_mode & 0o077 == 0


def test_a_record_carrying_a_secret_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(sessions.HOME_VARIABLE, str(tmp_path))
    (tmp_path / sessions.NAME).write_text(
        json.dumps(
            {
                "version": 1,
                "active": None,
                "connections": [{"name": "x", "refresh_token": "abc"}],
            }
        )
    )
    with pytest.raises(sessions.SessionError, match="refresh_token"):
        sessions.load()


def test_storage_that_would_not_protect_a_token_is_refused_before_sign_in(
    machine, monkeypatch
):
    assert sessions.storage("linux").protected is False or os.environ.get(
        "DBUS_SESSION_BUS_ADDRESS"
    )
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    assert sessions.storage("linux").protected is False
    assert sessions.storage("sunos5").protected is False
    assert sessions.storage("darwin").protected and sessions.storage("win32").protected


@needs_protected_storage
def test_a_sign_in_that_landed_in_plain_text_is_removed_and_the_login_fails(machine):
    leak = machine.root / "home" / ".m365pnppowershell" / "pnp.msal.cache"
    if sys.platform == "win32":
        pytest.skip("the cache directory is under LOCALAPPDATA on Windows")
    machine.collector.plaintext = leak
    out = _login(machine)
    assert out.returncode == 1
    assert "plain text" in out.stderr and "removed" in out.stderr
    assert not (machine.root / "record" / sessions.NAME).exists(), (
        "an exposed session was recorded"
    )
    assert [a["mode"] for a in machine.asked()] == ["Connect", "Logout"]
    assert machine.collector.kept == []


def test_a_plain_text_cache_is_recognised_and_an_opaque_one_is_not(tmp_path):
    plain, opaque = tmp_path / "a.cache", tmp_path / "b.cache"
    plain.write_text('{"RefreshToken": {"x": 1}}')
    opaque.write_bytes(bytes(range(256)))
    assert sessions.readable_token_cache([opaque, plain]) == plain
    assert sessions.readable_token_cache([opaque]) is None


# --- one tenant per connection -------------------------------------------------


@needs_protected_storage
def test_a_session_is_not_applied_to_another_tenant(machine):
    _login(machine)
    out = machine("collect", "sites", "--tenant-url", ELSEWHERE, "--output", "e")
    assert out.returncode == 2, (
        "the command had no identity of its own and must be refused"
    )
    assert "not used" in out.stderr and "fabrikam" in out.stderr
    assert len(machine.asked()) == 1, (
        "the other tenant was reached with this tenant's connection"
    )

    named = machine(
        "collect",
        "sites",
        "--connection",
        "contoso",
        "--tenant-url",
        ELSEWHERE,
        "--output",
        "e",
    )
    assert named.returncode == 2 and "cannot be used" in named.stderr
    assert len(machine.asked()) == 1


@needs_protected_storage
def test_the_command_line_and_the_project_file_win_over_the_connection(machine):
    _login(machine)
    machine(
        "collect",
        "sites",
        "--client-id",
        OTHER_CLIENT,
        "--tenant-url",
        TENANT,
        "--output",
        "e",
    )
    last = machine.asked()[-1]
    assert OTHER_CLIENT in last["argv"] and CLIENT not in last["argv"]
    assert last["interactive"], (
        "another application registration must sign in for itself"
    )


@needs_protected_storage
def test_two_connections_are_kept_apart_and_chosen_explicitly(machine):
    _login(machine)
    machine("login", "--client-id", CLIENT, "--tenant-url", ELSEWHERE)
    listed = json.loads(machine("connection", "list", "--format", "json").stdout)
    assert {row["name"]: row["active"] for row in listed} == {
        "contoso": False,
        "fabrikam": True,
    }

    assert machine("connection", "use", "contoso").returncode == 0
    machine("collect", "sites", "--output", "e")
    last = machine.asked()[-1]
    assert TENANT in last["argv"] and not last["interactive"]
    assert machine("connection", "use", "nobody").returncode == 2


@needs_protected_storage
def test_a_second_login_for_the_same_tenant_and_application_replaces_the_first(machine):
    _login(machine, "--name", "first")
    out = _login(machine, "--name", "second", "--format", "json")
    assert json.loads(out.stdout)["replaced"] == ["first"]
    assert [
        r["name"]
        for r in json.loads(machine("connection", "list", "--format", "json").stdout)
    ] == ["second"]


# --- status, expiry, logout ----------------------------------------------------


def test_status_reaches_no_tenant_and_says_logged_out_with_exit_one(machine):
    out = machine("status")
    assert out.returncode == 1 and "Logged out" in out.stdout
    assert machine.asked() == []


@needs_protected_storage
def test_status_describes_the_record_and_does_not_claim_a_check(machine):
    _login(machine)
    before = len(machine.asked())
    out = machine("status")
    assert out.returncode == 0
    assert (
        "contoso" in out.stdout and "interactive" in out.stdout and CLIENT in out.stdout
    )
    assert "not a check" in out.stdout
    assert (
        json.loads(machine("status", "--format", "json").stdout)["verified_now"]
        is False
    )
    assert len(machine.asked()) == before


@needs_protected_storage
def test_an_expired_or_revoked_session_is_reported_by_connect_as_not_established(
    machine,
):
    _login(machine)
    machine.collector.refuses = True
    out = machine("connect", "--format", "json")
    assert out.returncode == 1
    assert json.loads(out.stdout)["reach"] != "established"


@needs_protected_storage
def test_logout_clears_what_was_kept_and_then_the_next_collection_asks_again(machine):
    _login(machine)
    out = machine("logout")
    assert out.returncode == 0 and "stored sign-in removed" in out.stdout
    assert machine("status").returncode == 1
    machine(
        "collect",
        "sites",
        "--client-id",
        CLIENT,
        "--tenant-url",
        TENANT,
        "--output",
        "e",
    )
    assert machine.asked()[-1]["interactive"]


@needs_protected_storage
def test_a_logout_that_could_not_clear_keeps_the_record_and_fails(machine):
    _login(machine)
    machine.collector.refuses = True
    out = machine("logout")
    assert out.returncode == 1 and "NOT removed" in out.stderr
    assert machine("status").returncode == 0, (
        "the record was dropped while the sign-in is still stored"
    )


def test_a_certificate_connection_keeps_nothing(machine, tmp_path):
    certificate = tmp_path / "app.pfx"
    certificate.write_bytes(b"not a real certificate")
    out = machine(
        "login",
        "--client-id",
        CLIENT,
        "--tenant-url",
        TENANT,
        "--tenant-id",
        "contoso.onmicrosoft.com",
        "--certificate-path",
        str(certificate),
        "--format",
        "json",
    )
    assert out.returncode == 0, out.stderr
    said = json.loads(out.stdout)
    assert (
        said["record"]["persisted"] is False
        and said["record"]["method"] == "certificate"
    )
    assert not [a for a in machine.asked() if "-PersistLogin" in a["argv"]]
    assert machine("logout").returncode == 0
    assert [a["mode"] for a in machine.asked()] == ["Connect"], (
        "logging out of a certificate reached the tenant"
    )


# --- the collector's own refusals ----------------------------------------------


def test_the_collector_accepts_a_kept_sign_in_in_the_connect_mode_only():
    script = (collecting.COLLECTOR).read_text(encoding="utf-8")
    assert "if ($PersistLogin -and $Mode -ne 'Connect')" in script
    assert "Disconnect-PnPOnline -ClearPersistedLogin" in script


def test_the_licensing_collector_keeps_its_sign_in_to_its_own_process():
    script = collecting.SLICES["licensing"].collector.read_text(encoding="utf-8")
    delegated = [
        line for line in script.splitlines() if "Connect-MgGraph -Scopes" in line
    ]
    assert delegated and all("-ContextScope Process" in line for line in delegated)


# --- a login that did not end in a session leaves nothing set to be kept --------


def _library_settings(home: Path, entries: list[dict]) -> Path:
    directory = home / ".m365pnppowershell"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "settings.json"
    path.write_text(json.dumps({"Cache": entries}))
    return path


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="the library's directory is under LOCALAPPDATA on Windows",
)
@needs_protected_storage
def test_a_login_that_was_refused_undoes_the_decision_to_keep_sign_ins(machine):
    """The library writes that decision before the sign-in (first live attempt)."""
    other = {
        "Url": "https://fabrikam.sharepoint.com",
        "ClientId": CLIENT,
        "Enabled": True,
    }
    path = _library_settings(
        machine.root / "home",
        [
            {
                "Url": "https://contoso.sharepoint.com",
                "ClientId": CLIENT.upper(),
                "Enabled": True,
            },
            other,
        ],
    )
    machine.collector.refuses = True
    out = _login(machine)
    assert out.returncode == 1 and "Not logged in" in out.stdout
    assert json.loads(path.read_text())["Cache"] == [other], (
        "another tenant's entry was touched, or ours was left"
    )
    assert not (machine.root / "record" / sessions.NAME).exists()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="the library's directory is under LOCALAPPDATA on Windows",
)
def test_status_names_a_kept_sign_in_no_connection_accounts_for(machine):
    _library_settings(
        machine.root / "home",
        [
            {
                "Url": "https://contoso.sharepoint.com",
                "ClientId": CLIENT,
                "Enabled": True,
            }
        ],
    )
    out = machine("status")
    assert (
        "contoso.sharepoint.com" in out.stderr
        and "no connection here records one" in " ".join(out.stderr.split())
    )
    assert json.loads(machine("status", "--format", "json").stdout)["unrecorded"] == [
        "contoso.sharepoint.com"
    ]


# --- the rest of what the commands say and refuse ------------------------------


@needs_protected_storage
def test_login_in_text_says_where_the_session_is_kept_and_how_to_remove_it(machine):
    out = _login(machine, "--name", "work")
    assert out.returncode == 0
    assert "Logged in." in out.stdout and "work (active)" in out.stdout
    assert "stored in" in out.stdout and "logout" in out.stdout
    again = _login(machine, "--name", "other")
    assert "replaced    work" in again.stdout


def test_login_needs_an_address_and_a_dry_run_reaches_nothing(machine):
    assert machine("login", "--client-id", CLIENT).returncode == 2
    out = _login(machine, "--dry-run")
    assert out.returncode == 0 and "-PersistLogin" in out.stdout
    assert machine.asked() == [] and not (machine.root / "record").exists()


def test_login_is_refused_where_storage_would_not_protect_the_token(
    machine, monkeypatch
):
    monkeypatch.setattr(
        sessions, "storage", lambda: sessions.Storage(False, "no keyring is running")
    )
    out = _login(machine)
    assert out.returncode == 2
    assert "refusing to keep a session" in out.stderr and "no keyring" in out.stderr
    assert machine.asked() == [], "a sign-in was attempted before the refusal"


@needs_protected_storage
def test_the_connection_commands_list_choose_and_remove(machine):
    assert "No stored connections" in machine("connection", "list").stdout
    _login(machine)
    machine("login", "--client-id", CLIENT, "--tenant-url", ELSEWHERE, "--device-login")
    listed = machine("connection", "list").stdout
    assert "contoso" in listed and "fabrikam (active)" in listed
    assert "device-code" in listed

    assert machine("connection", "remove", "nobody").returncode == 2
    assert machine("connection", "remove", "contoso").returncode == 0
    assert machine("logout", "--name", "nobody").returncode == 2
    assert machine("logout", "--name", "x", "--all").returncode == 2
    assert machine("logout", "--all").returncode == 0
    assert machine("logout").returncode == 0, "logging out twice is not an error"
    assert machine.collector.kept == []
    assert json.loads(machine("connection", "list", "--format", "json").stdout) == []


@needs_protected_storage
def test_removing_the_active_connection_promotes_nobody(machine):
    _login(machine)
    machine("login", "--client-id", CLIENT, "--tenant-url", ELSEWHERE)
    machine("logout")
    out = machine("status")
    assert out.returncode == 1 and "1 stored" in out.stdout


@needs_protected_storage
def test_a_named_connection_that_does_not_exist_is_a_refusal(machine):
    out = machine("collect", "sites", "--connection", "nobody", "--output", "e")
    assert out.returncode == 2 and "no connection named nobody" in out.stderr
    assert machine("connect", "--connection", "nobody").returncode == 2


def test_an_unreadable_record_is_a_refusal_and_never_a_guess(machine):
    record = machine.root / "record"
    record.mkdir()
    (record / sessions.NAME).write_text("{not json")
    for argv in (["status"], ["logout"], ["connection", "list"]):
        assert machine(*argv).returncode == 2, argv
    out = machine("collect", "sites", "--tenant-url", TENANT, "--output", "e")
    assert out.returncode == 2 and "cannot be read" in out.stderr
    (record / sessions.NAME).write_text(json.dumps({"version": 99}))
    assert machine("status").returncode == 2


def test_the_store_refuses_what_it_cannot_describe(tmp_path):
    store = sessions.Store(path=tmp_path / sessions.NAME)
    bad = sessions.Connection(
        name="x",
        tenant_url=TENANT,
        client_id=CLIENT,
        method="password",
        persisted=True,
        logged_in_at="2026-11-11T00:00:00Z",
    )
    with pytest.raises(sessions.SessionError, match="unknown sign-in method"):
        store.add(bad)
    with pytest.raises(sessions.SessionError):
        store.remove("x")
    with pytest.raises(sessions.SessionError):
        store.use("x")
    assert sessions.tenant_key("https://contoso-my.sharepoint.com/x") == (
        "contoso.sharepoint.com"
    )
    assert sessions.tenant_key("localhost") == "localhost"
    assert sessions.default_name(TENANT) == "contoso"


def test_the_linux_keyring_is_asked_and_believed_only_when_it_answers(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setattr(sessions.shutil, "which", lambda name: None)
    assert "dbus-send" in sessions.storage("linux").detail

    monkeypatch.setattr(sessions.shutil, "which", lambda name: "/usr/bin/dbus-send")
    answers = iter(
        [
            SimpleNamespace(returncode=0, stdout="   boolean true\n"),
            SimpleNamespace(returncode=0, stdout="   boolean false\n"),
        ]
    )
    monkeypatch.setattr(sessions.subprocess, "run", lambda *a, **k: next(answers))
    assert sessions.storage("linux").protected is True
    assert sessions.storage("linux").protected is False

    def unanswered(*a, **k):
        raise OSError("no bus")

    monkeypatch.setattr(sessions.subprocess, "run", unanswered)
    assert sessions.storage("linux").protected is False


def test_the_record_lives_where_the_platform_keeps_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv(sessions.HOME_VARIABLE, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    for platform, expected in (
        ("linux", tmp_path / "xdg" / "m365g"),
        ("win32", tmp_path / "roaming" / "m365g"),
        ("darwin", tmp_path / "Library" / "Application Support" / "m365g"),
    ):
        monkeypatch.setattr(sessions.sys, "platform", platform)
        assert sessions.home() == expected


def test_a_certificate_connection_supplies_the_certificate_to_later_commands(
    machine, tmp_path, monkeypatch
):
    certificate = tmp_path / "app.pfx"
    certificate.write_bytes(b"not a real certificate")
    monkeypatch.setenv("APP_PFX_PASSWORD", "x")
    machine(
        "login", "--client-id", CLIENT, "--tenant-url", TENANT,
        "--tenant-id", "contoso.onmicrosoft.com",
        "--certificate-path", certificate,
        "--certificate-password-env", "APP_PFX_PASSWORD",
    )  # fmt: skip
    out = machine("collect", "sites", "--output", "e")
    last = machine.asked()[-1]["argv"]
    assert "-CertificatePath" in last and "-CertificatePasswordEnv" in last
    assert "APP_PFX_PASSWORD" in last and "x" not in last, "the value travelled"
    assert "certificate_path" in out.stderr and "tenant_id" in out.stderr


@needs_protected_storage
def test_a_command_that_chooses_its_own_sign_in_does_not_use_the_connection(machine):
    _login(machine)
    out = machine("collect", "sites", "--device-login", "--output", "e")
    assert "chose its own sign-in method" in out.stderr
    assert out.returncode == 2, "it has no application registration of its own"

    machine("login", "--client-id", CLIENT, "--tenant-url", TENANT, "--device-login")
    machine("collect", "sites", "--output", "e")
    assert "-DeviceLogin" in machine.asked()[-1]["argv"]


@needs_protected_storage
def test_a_login_that_did_not_open_says_so_to_a_consumer_too(machine):
    machine.collector.refuses = True
    out = _login(machine, "--format", "json")
    said = json.loads(out.stdout)
    assert out.returncode == 1 and said["logged_in"] is False
    assert said["connection"]["reach"] != "established"


def test_a_connect_that_fails_after_signing_in_removes_the_kept_sign_in():
    """The library stores the sign-in when the session opens. A failure after
    that reports no session, so it may not leave a stored one behind."""
    script = (collecting.COLLECTOR).read_text(encoding="utf-8")
    connect = script.rsplit("\nif ($Mode -eq 'Connect') {", 1)[1].split("\nif (", 1)[0]
    caught = connect.split("catch {", 1)[1]
    assert "if ($PersistLogin)" in caught
    assert "Disconnect-PnPOnline -ClearPersistedLogin" in caught
    assert "throw" in caught


def test_the_session_facts_read_claims_and_no_property_the_library_dropped():
    """PnP.PowerShell 3.4.1 has no Scopes property on its connection: reading
    it under strict mode ended the first live login on that version."""
    module = (collecting.COLLECTOR.parent / "modules" / "Connection.psm1").read_text(
        encoding="utf-8"
    )
    facts = module.split("function Get-ConnectionFacts", 1)[1].split("\nfunction ", 1)[
        0
    ]
    code = "\n".join(
        line for line in facts.splitlines() if not line.strip().startswith("#")
    )
    assert "$connection.Scopes" not in code
    assert "Get-PnPAccessToken -ResourceTypeName SharePoint -Decoded" in code
    for claim in ("'scp'", "'roles'", "'tid'"):
        assert claim in code
    # The token is read for three claims and is never written anywhere.
    assert "Write-Host" not in code and "Write-Output" not in code
