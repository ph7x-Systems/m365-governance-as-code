"""Setting a machine up for a person who does not know what any of it is.

`D90`, the owner's decision of 2026-11-06: a person who is not an administrator
installs the command line, runs `setup`, and reaches a first report without
knowing what Entra ID, PnP.PowerShell or an application registration is. So
`setup` does the steps rather than describing them:

- it checks PowerShell 7 and PnP.PowerShell, and installs or updates them to
  their latest stable release when the person agrees, or says exactly what to
  install where it cannot;
- it asks for the SharePoint address and derives the rest;
- it obtains the application registration: it registers it itself when the
  person is an administrator and agrees, and it prepares the request an
  administrator acts on when they are not.

THE ONE WRITE. Registering the application is the only write this engine makes
to a tenant, and it is made here and nowhere else: on the person's explicit
agreement, interactively, under an administrator's own sign-in and consent,
with only the permissions the collectors read under. Collection, evaluation
and every other command still have no write path under any flag, and the
engine still acquires no authentication of its own: the sign-in is always the
person's, in a browser PnP.PowerShell opens.

Nothing here runs without a terminal to ask in, unless a flag says so: a
pipeline that ran `setup` used to get a report and a printed command, and that
is still what it gets.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

#: What the registration asks for, and nothing more. Without named permissions
#: PnP asks for AllSites.FullControl, Group.ReadWrite.All, User.ReadWrite.All
#: and TermStore.ReadWrite.All. The collectors call only PnP `Get-` cmdlets:
#: SharePoint answers its permission and tenant-setting reads only under
#: AllSites.FullControl (AllSites.Read fails them, docs/COLLECTOR-LIVE-MATRIX.md),
#: and Microsoft Graph is needed only to sign in.
SHAREPOINT_PERMISSIONS = ("AllSites.FullControl",)
GRAPH_PERMISSIONS = ("User.Read",)
APPLICATION_NAME = "M365 Governance"

#: How PowerShell itself is installed and updated, where one command is right.
#: Linux keeps Microsoft's page: the command differs by distribution.
POWERSHELL_COMMANDS = {
    "Darwin": (
        ["brew", "install", "--cask", "powershell"],
        ["brew", "upgrade", "--cask", "powershell"],
    ),
    "Windows": (
        ["winget", "install", "--id", "Microsoft.PowerShell", "--source", "winget"],
        ["winget", "upgrade", "--id", "Microsoft.PowerShell", "--source", "winget"],
    ),
}
POWERSHELL_DOCS = "https://aka.ms/powershell-release"
#: Microsoft's own link to the current stable release: it ends on the release's
#: tag, which names the version, so nothing else has to be asked.
POWERSHELL_LATEST = POWERSHELL_DOCS + "?tag=stable"

GUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class RegistrationFailed(Exception):
    """The registration was attempted and did not produce an id.

    `kind` is what a person does next: `exists` (use the one that is there),
    `not-administrator` (ask somebody who is) or `failed` (read the reason).
    """

    def __init__(self, kind: str, reason: str):
        super().__init__(reason)
        self.kind = kind


@dataclass
class Asker:
    """Asks a person, or answers for them where a flag already did.

    Without a terminal nothing is asked and nothing is agreed, so a pipeline
    that runs `setup` gets the report and the printed commands, as before.
    """

    interactive: bool
    install: bool = False
    register: bool = False

    def agree(self, question: str, *, flag: bool = False, default: bool = True) -> bool:
        if flag:
            return True
        if not self.interactive:
            return False
        suffix = " [Y/n] " if default else " [y/N] "
        answer = input(question + suffix).strip().lower()
        return default if not answer else answer in ("y", "yes", "s", "sim")

    def ask(self, question: str) -> str:
        if not self.interactive:
            return ""
        return input(question).strip()


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run(
    command: list[str], *, capture: bool = False, timeout: int = 1800
) -> subprocess.CompletedProcess:
    # The person sees an installer's own progress, so its output is not captured.
    return subprocess.run(command, capture_output=capture, text=True, timeout=timeout)


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def _latest_powershell() -> str | None:
    """The latest stable PowerShell, or None when it cannot be asked."""
    try:
        request = urllib.request.Request(
            POWERSHELL_LATEST, headers={"User-Agent": "m365-governance-setup"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            found = re.search(r"/tag/v(\d+\.\d+\.\d+)$", response.geturl())
        return found.group(1) if found else None
    except Exception:  # noqa: BLE001 - an offline machine still gets set up
        return None


def _pwsh_version(pwsh: str) -> str:
    done = _run(
        [pwsh, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
        capture=True,
        timeout=90,
    )
    return done.stdout.strip()


def ensure_powershell(asker: Asker, say) -> str | None:
    """PowerShell 7 at its latest stable release, or what to do about it."""
    system = platform.system()
    commands = POWERSHELL_COMMANDS.get(system)
    pwsh = shutil.which("pwsh")
    if not pwsh:
        if (
            commands
            and shutil.which(commands[0][0])
            and asker.agree(
                "PowerShell 7 is not installed. The collectors run in it. "
                "Install it now?",
                flag=asker.install,
            )
        ):
            _run(commands[0])
            pwsh = shutil.which("pwsh")
        if not pwsh:
            where = " ".join(commands[0]) if commands else POWERSHELL_DOCS
            say(f"PowerShell 7 is needed for the collectors. Install it: {where}")
            return None
    latest = _latest_powershell()
    current = _pwsh_version(pwsh)
    if latest and current and _version_tuple(current) < _version_tuple(latest):
        if system == "Darwin" and shutil.which("brew"):
            # Homebrew holds PowerShell as a formula or as a cask; update the
            # one that is there.
            formula = _run(
                ["brew", "list", "--versions", "powershell"], capture=True, timeout=120
            ).stdout.strip()
            commands = (
                commands[0],
                ["brew", "upgrade", "powershell"] if formula else commands[1],
            )
        if (
            commands
            and shutil.which(commands[1][0])
            and asker.agree(
                f"PowerShell {current} is installed; the latest stable release "
                f"is {latest}. Update it now?",
                flag=asker.install,
            )
        ):
            _run(commands[1])
        else:
            where = " ".join(commands[1]) if commands else POWERSHELL_DOCS
            say(
                f"PowerShell {current} is older than the latest stable release, "
                f"{latest}. Update it: {where}"
            )
    return pwsh


def _pnp_installed(pwsh: str) -> str:
    done = _run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "(Get-Module -ListAvailable PnP.PowerShell | Sort-Object Version "
            "-Descending | Select-Object -First 1).Version.ToString()",
        ],
        capture=True,
        timeout=120,
    )
    return done.stdout.strip()


def _pnp_latest(pwsh: str) -> str:
    done = _run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "(Find-Module PnP.PowerShell -Repository PSGallery).Version.ToString()",
        ],
        capture=True,
        timeout=120,
    )
    return done.stdout.strip()


def ensure_pnp(pwsh: str, asker: Asker, say) -> bool:
    """PnP.PowerShell at its latest stable release, installed for this user only.

    No administrator is needed: `-Scope CurrentUser` writes to the person's own
    module folder.
    """
    installed = _pnp_installed(pwsh)
    latest = _pnp_latest(pwsh)
    install = (
        "Install-Module PnP.PowerShell -Scope CurrentUser -Force -Repository PSGallery"
    )
    if installed and (
        not latest or _version_tuple(installed) >= _version_tuple(latest)
    ):
        return True
    question = (
        f"PnP.PowerShell {installed} is installed; the latest stable release is "
        f"{latest}. Update it now?"
        if installed
        else "PnP.PowerShell is not installed. The SharePoint collectors use it. "
        "Install it now?"
    )
    if asker.agree(question, flag=asker.install):
        _run(
            [
                pwsh,
                "-NoProfile",
                "-Command",
                install + (f" -RequiredVersion {latest}" if latest else ""),
            ]
        )
        installed = _pnp_installed(pwsh)
    if not installed:
        say(
            "PnP.PowerShell is needed for the SharePoint collectors. In "
            f"PowerShell: {install}"
        )
        return False
    if latest and _version_tuple(installed) < _version_tuple(latest):
        say(
            f"PnP.PowerShell {installed} is older than the latest stable release, "
            f"{latest}. In PowerShell: {install}"
        )
    return True


def target_from(answer: str) -> tuple[str, str] | None:
    """`contoso`, `contoso.sharepoint.com` or any address on it.

    Returns the admin centre and the root site.
    """
    match = re.search(
        r"([a-z0-9][a-z0-9-]*?)(?:-admin|-my)?\.sharepoint\.com", answer.lower()
    )
    name = match.group(1) if match else answer.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""):
        return None
    return f"https://{name}-admin.sharepoint.com", f"https://{name}.sharepoint.com"


def tenant_domain(tenant_url: str | None, site_url: str | None) -> str | None:
    """The `<tenant>.onmicrosoft.com` PnP registers in, from either address."""
    for url in (tenant_url, site_url):
        match = re.search(
            r"https://([a-z0-9-]+?)(?:-admin)?\.sharepoint\.com", (url or "").lower()
        )
        if match:
            return f"{match.group(1)}.onmicrosoft.com"
    return None


def registration_command(
    tenant: str, name: str = APPLICATION_NAME, device_login: bool = False
) -> str:
    """The one command, on one line, as a person or an administrator pastes it."""
    return (
        "Register-PnPEntraIDAppForInteractiveLogin "
        f'-ApplicationName "{name}" -Tenant {tenant} '
        f"-SharePointDelegatePermissions {','.join(SHAREPOINT_PERMISSIONS)} "
        f"-GraphDelegatePermissions {','.join(GRAPH_PERMISSIONS)}"
        + (" -DeviceLogin" if device_login else "")
    )


def register(
    pwsh: str,
    tenant: str,
    *,
    agreed: bool,
    name: str = APPLICATION_NAME,
    device_login: bool = False,
) -> str:
    """Register the application, and return its id. THE ONE WRITE.

    Refused unless the person agreed: this is the only place the engine writes
    to a tenant, and it never does so by default or as a side effect.
    """
    if not agreed:
        raise RegistrationFailed(
            "failed", "the registration was not agreed to, so nothing was registered"
        )
    script = (
        "$ErrorActionPreference = 'Stop'; Import-Module PnP.PowerShell; "
        f"$r = {registration_command(tenant, name, device_login)}; "
        "$id = $r.'AzureAppId/ClientId'; if (-not $id) { $id = $r.AzureAppId }; "
        "Write-Output ('CLIENT_ID=' + $id)"
    )
    done = _run([pwsh, "-NoProfile", "-Command", script], capture=True)
    output = (done.stdout or "") + (done.stderr or "")
    found = re.search(r"CLIENT_ID=(" + GUID.pattern + ")", output)
    if done.returncode == 0 and found:
        return found.group(1)
    lowered = output.lower()
    if "already exists" in lowered:
        raise RegistrationFailed(
            "exists", f'an application named "{name}" already exists in {tenant}'
        )
    if any(
        word in lowered
        for word in (
            "insufficient privileges",
            "authorization_requestdenied",
            "forbidden",
            "admin approval",
            "not authorized",
        )
    ):
        raise RegistrationFailed(
            "not-administrator",
            "this account cannot register applications or consent to them",
        )
    tail = (
        output.strip().splitlines()[-1] if output.strip() else f"exit {done.returncode}"
    )
    raise RegistrationFailed("failed", tail)


def administrator_request(
    path: Path, tenant: str | None, target: str, name: str = APPLICATION_NAME
) -> Path:
    """What an administrator reads and acts on, written where the person can send it."""
    tenant_text = tenant or "<your-tenant>.onmicrosoft.com"
    text = f"""\
Request: register the "{name}" application for M365 Governance as Code

M365 Governance as Code reads this organisation's SharePoint configuration and
reports what it can establish. It needs one Entra ID application registration,
created once by an administrator. It reads only: the collectors call PnP Get-
cmdlets and nothing else.

In PowerShell 7 with PnP.PowerShell, signed in as an administrator:

    {registration_command(tenant_text, name)}

A browser opens to sign in and consent. The permissions are SharePoint
AllSites.FullControl, delegated (SharePoint answers its permission and
tenant-setting reads only under it), and Microsoft Graph User.Read, to sign in.

It prints the id of the registration. Send that id back. Then:

    m365-governance setup --client-id <id> {target}
"""
    path.write_text(text, encoding="utf-8")
    return path
