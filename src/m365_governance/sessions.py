"""Connections a person chose to keep, and nothing that could open one.

A session survives a command only after `login`, which is the operator's
explicit choice (docs/CLI.md). What is kept HERE is a description: which
tenant, which application registration, which sign-in method, who the session
said it was, and when. The token is not here and never passes through this
process: the sign-in library writes it into the operating system's protected
storage, and this module's part is to refuse the cases where it would not.

THREE THINGS THIS FILE REFUSES, AND THEY ARE THE POINT OF IT.

A secret. The record is a file a person can read, so it holds names and
addresses. A key that looks like a credential is refused when written and when
read, the same refusal a project file makes.

Plain-text persistence. On Linux the sign-in library falls back to an
unprotected file when no keyring answers. `storage()` says whether protected
storage can be established before anybody signs in, and `readable_token_cache`
looks at the result afterwards, because a check made before the act is a
belief and the file on disk is the fact.

Another tenant. A connection is for one tenant. `covers` is how a command asks
whether the address it was given belongs to the connection it is about to use,
and a session is never applied to an address it does not cover.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

#: Overrides where the record lives. For tests, and for an operator who keeps
#: configuration somewhere of their own.
HOME_VARIABLE = "M365G_HOME"

NAME = "connections.json"

VERSION = 1

#: Field names a record may never carry. The method and the NAME of a variable
#: are descriptions; a value under one of these would be the credential itself.
FORBIDDEN = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "secret",
        "client_secret",
        "password",
        "certificate_password",
        "assertion",
        "cookie",
    }
)

METHODS = ("interactive", "device-code", "certificate")


class SessionError(Exception):
    """A record that cannot be trusted, or a request it cannot satisfy."""


@dataclass(frozen=True)
class Connection:
    """One connection, as a description. No field here can open a session."""

    name: str
    tenant_url: str
    client_id: str
    method: str
    #: Whether a token for it was persisted by the sign-in library. False for a
    #: certificate: nothing interactive was saved, the certificate signs in.
    persisted: bool
    logged_in_at: str
    #: What the session said about itself when it opened. Reported, not proved.
    identity_kind: str = "not-established"
    identity: str | None = None
    tenant_id: str | None = None
    certificate_path: str | None = None
    #: The NAME of an environment variable. Never its value.
    certificate_password_env: str | None = None

    @property
    def tenant(self) -> str:
        return tenant_key(self.tenant_url)

    def covers(self, url: str | None) -> bool:
        """Whether an address belongs to the tenant this connection is for."""
        return url is None or tenant_key(url) == self.tenant


@dataclass
class Store:
    path: Path
    connections: list[Connection] = field(default_factory=list)
    active: str | None = None

    def get(self, name: str) -> Connection | None:
        return next((c for c in self.connections if c.name == name), None)

    def current(self) -> Connection | None:
        return self.get(self.active) if self.active else None

    def add(self, connection: Connection) -> list[str]:
        """Record a connection and make it the active one.

        Returns the names it replaced. One identity per tenant and application
        registration: the sign-in library keys a persisted token by those two,
        and which account it would choose among several is not established, so
        a second connection for the same pair replaces the first rather than
        pretending two can be told apart.
        """
        if connection.method not in METHODS:
            raise SessionError(f"unknown sign-in method: {connection.method}")
        replaced = [
            c.name
            for c in self.connections
            if c.name == connection.name
            or (
                c.tenant == connection.tenant
                and c.client_id.lower() == connection.client_id.lower()
            )
        ]
        self.connections = [c for c in self.connections if c.name not in replaced]
        self.connections.append(connection)
        self.active = connection.name
        return [name for name in replaced if name != connection.name]

    def remove(self, name: str) -> None:
        if self.get(name) is None:
            raise SessionError(f"no connection named {name}")
        self.connections = [c for c in self.connections if c.name != name]
        if self.active == name:
            # NOTHING IS PROMOTED. The next command would otherwise run as an
            # identity nobody selected, on the strength of having been listed
            # first.
            self.active = None

    def use(self, name: str) -> Connection:
        found = self.get(name)
        if found is None:
            raise SessionError(f"no connection named {name}")
        self.active = name
        return found

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(self.path.parent, 0o700)
        document = {
            "version": VERSION,
            "active": self.active,
            "connections": [asdict(c) for c in self.connections],
        }
        _refuse_secrets(document)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        temporary.replace(self.path)


def home() -> Path:
    """Where this user's record lives, by the platform's own convention."""
    named = os.environ.get(HOME_VARIABLE)
    if named:
        return Path(named)
    if sys.platform == "win32":
        return (
            Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
            / "m365g"
        )
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "m365g"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "m365g"


def load() -> Store:
    path = home() / NAME
    if not path.exists():
        return Store(path=path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"{path} cannot be read: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("version") != VERSION:
        raise SessionError(f"{path} is not a version {VERSION} connections file")
    _refuse_secrets(raw, where=str(path))
    try:
        connections = [Connection(**entry) for entry in raw.get("connections", [])]
    except TypeError as exc:
        raise SessionError(
            f"{path} holds a connection this version cannot read: {exc}"
        ) from exc
    active = raw.get("active")
    store = Store(path=path, connections=connections, active=active)
    if active and store.get(active) is None:
        store.active = None
    return store


def _refuse_secrets(value: Any, where: str = "a connection record") -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            if str(key).lower() in FORBIDDEN:
                raise SessionError(
                    f"{where} carries `{key}`. A connection is a description: "
                    f"tokens live in the operating system's protected storage "
                    f"and a certificate's password in an environment variable "
                    f"this file only names."
                )
            _refuse_secrets(inner, where)
    elif isinstance(value, list):
        for inner in value:
            _refuse_secrets(inner, where)


def tenant_key(url: str) -> str:
    """One name for a tenant's three SharePoint hosts.

    `contoso`, `contoso-admin` and `contoso-my` are one tenant, and the sign-in
    library keys a persisted token the same way. Anything that is not a host of
    that shape is its own key, so two unrelated addresses are never one tenant.
    """
    host = (urlparse(url).hostname or url).lower()
    first, _, rest = host.partition(".")
    for suffix in ("-admin", "-my"):
        if first.endswith(suffix):
            first = first[: -len(suffix)]
            break
    return f"{first}.{rest}" if rest else first


def default_name(url: str) -> str:
    return tenant_key(url).split(".")[0]


@dataclass(frozen=True)
class Storage:
    """Whether a persisted token would be protected on this machine."""

    protected: bool
    #: The storage, where it is established; the reason, where it is not.
    detail: str


def storage(platform: str | None = None) -> Storage:
    """Say where a persisted token would be kept. Reaches no tenant.

    macOS and Windows have protected storage the sign-in library always uses.
    Linux has it only when a secret service is running on the session bus, and
    without one the library writes the tokens to an unprotected file: that
    case is refused before anybody signs in.
    """
    platform = platform or sys.platform
    if platform == "darwin":
        return Storage(True, "the macOS Keychain")
    if platform == "win32":
        return Storage(True, "Windows data protection (DPAPI), for this user")
    if platform.startswith("linux"):
        if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            return Storage(False, "no session bus, so no keyring can answer")
        probe = shutil.which("dbus-send")
        if probe is None:
            return Storage(
                False, "dbus-send is not installed, so the keyring cannot be asked"
            )
        try:
            answered = subprocess.run(
                [
                    probe,
                    "--session",
                    "--print-reply",
                    "--dest=org.freedesktop.DBus",
                    "/org/freedesktop/DBus",
                    "org.freedesktop.DBus.NameHasOwner",
                    "string:org.freedesktop.secrets",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return Storage(False, "the session bus did not answer")
        if answered.returncode == 0 and "boolean true" in answered.stdout:
            return Storage(True, "the Linux keyring (Secret Service)")
        return Storage(False, "no keyring (Secret Service) is running in this session")
    return Storage(False, f"protected storage is not established on {platform}")


def _library_directory() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path.home()
    return root / ".m365pnppowershell"


def kept_registrations() -> list[tuple[str, str]]:
    """The tenants and applications the sign-in library keeps sign-ins for.

    The library records that decision in its own settings file BEFORE anybody
    signs in, so a login that was cancelled or refused leaves the decision
    behind with no session: the next ordinary sign-in for that pair would be
    kept without anybody asking. Read here so that it can be seen and undone.
    """
    path = _library_directory() / "settings.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = raw.get("Cache") if isinstance(raw, dict) else None
    return [
        (tenant_key(str(e.get("Url", ""))), str(e.get("ClientId", "")).lower())
        for e in entries or []
        if isinstance(e, dict)
        and e.get("Enabled")
        and str(e.get("AuthenticationType", "")).lower() != "apponly"
    ]


def forget_registration(tenant_url: str, client_id: str) -> bool:
    """Undo the library's decision to keep sign-ins for one tenant and application.

    Used when a login did not end in a session. Removes that one entry and
    leaves every other one, and the tokens of other connections, untouched.
    Returns whether an entry was removed.
    """
    path = _library_directory() / "settings.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    entries = raw.get("Cache") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return False
    wanted = (tenant_key(tenant_url), client_id.lower())
    kept = [
        e
        for e in entries
        if not (
            isinstance(e, dict)
            and (tenant_key(str(e.get("Url", ""))), str(e.get("ClientId", "")).lower())
            == wanted
            and str(e.get("AuthenticationType", "")).lower() != "apponly"
        )
    ]
    if len(kept) == len(entries):
        return False
    raw["Cache"] = kept
    path.write_text(json.dumps(raw), encoding="utf-8")
    return True


def token_cache_files() -> list[Path]:
    """Where the sign-in library keeps its delegated token cache file."""
    directory = _library_directory()
    return sorted(directory.glob("pnp.msal*.cache")) if directory.is_dir() else []


def readable_token_cache(files: list[Path] | None = None) -> Path | None:
    """The token cache file that can be read as plain text, if there is one.

    Protected storage leaves either no token in the file or an encrypted blob.
    A file that decodes as text and names its tokens is the unprotected
    fallback, whatever was believed before the sign-in.
    """
    for path in token_cache_files() if files is None else files:
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if '"RefreshToken"' in text or '"AccessToken"' in text:
            return path
    return None
