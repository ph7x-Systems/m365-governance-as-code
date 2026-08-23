"""Spending the application registration the rest of the engine already has.

THE DEFECT THIS CLOSES, NAMED PLAINLY. Every PowerShell collector in this
engine authenticates as an application, with `--client-id`, `--tenant-id` and
`--certificate-path`. The command line accepts them, `_authentication` refuses
an ambiguous combination of them, and then the Graph slices ignored all of it
and demanded a bearer token pasted into an environment variable by a person.

A command-line tool that holds an application registration and asks a human to
fetch it a token is not a command-line tool. Worse, it made every Graph slice
depend on somebody being at a keyboard, which is the difference between a
capability that runs on a schedule and one that runs when a person remembers.

WHY POWERSHELL AND NOT A LIBRARY. Minting an application-only token means
signing a client assertion with the certificate's private key, and this engine
declares two dependencies: PyYAML and jsonschema. Adding a cryptography stack
to a public MIT engine to duplicate something already installed on every
machine that runs the collectors is a second authentication model to keep
correct, and the first time the two disagree the evidence says one identity
while another was used. PnP.PowerShell already holds the credential and
already issues this token; this runs it and reads what it printed.

WHAT THIS MODULE WILL NOT DO. It does not acquire consent, register an
application, cache a token, write one to disk, or put one in a process
argument. The certificate password is read from the environment by name, in the
child process, and never travels through this one. What it returns is a string
its caller spends immediately and nothing keeps.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: How the child process is run. A parameter rather than a call, because the
#: defect this module closes survived for as long as it did precisely because
#: the path could not be exercised without a tenant: the token came from an
#: environment variable, so nothing tested what happened around it. Every
#: branch below is now reachable from a test that reaches no directory.
Runner = Callable[[list[str]], Any]


class Unavailable(Exception):
    """No token was produced, and the reason is a sentence rather than a code."""


@dataclass(frozen=True)
class Application:
    """The registration a token is asked for, and never the credential itself.

    `certificate_password_env` is the NAME of an environment variable. A field
    holding the password would put it in every stack trace and every repr, and
    the point of naming it is that this process never reads it.
    """

    client_id: str
    tenant_id: str
    certificate_path: str
    tenant_url: str
    certificate_password_env: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.client_id and self.tenant_id and self.certificate_path)


#: The script the child runs. Written as one string with the values passed
#: SEPARATELY as PowerShell parameters rather than interpolated: a tenant
#: identifier that arrived from a project file is not a place to build a
#: command out of string addition.
SCRIPT = """
param($ClientId, $TenantId, $CertificatePath, $Url, $PasswordEnv)
$ErrorActionPreference = 'Stop'
Import-Module PnP.PowerShell -ErrorAction Stop
$connect = @{
    Url          = $Url
    ClientId     = $ClientId
    Tenant       = $TenantId
    CertificatePath = $CertificatePath
}
if ($PasswordEnv) {
    $secret = [Environment]::GetEnvironmentVariable($PasswordEnv)
    if (-not $secret) { throw "$PasswordEnv is not set in this process" }
    $connect.CertificatePassword = (ConvertTo-SecureString $secret -AsPlainText -Force)
}
Connect-PnPOnline @connect
# The token, and nothing else on standard output. A collector reads this
# stream; a line of progress printed here would be read as a credential.
Get-PnPAccessToken -ResourceTypeName Graph
"""


def acquire(
    application: Application, *, timeout: int = 120, run: Runner | None = None
) -> str:
    """One application-only Graph token, from the certificate.

    THIS REACHES A DIRECTORY. It is the authorization boundary of the whole
    engine and the only function here that crosses it. Everything above is
    preparation, and preparation is never permission: a caller reaching this
    has been told to connect to this tenant, by somebody, for this operation.
    """
    if not application.complete:
        raise Unavailable(
            "an application-only Graph token needs a client id, a tenant id "
            "and a certificate. Supply --client-id, --tenant-id and "
            "--certificate-path, or record them once in the project file."
        )

    runner = run if run is not None else _subprocess(timeout)
    argv = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        SCRIPT,
        "-ClientId",
        application.client_id,
        "-TenantId",
        application.tenant_id,
        "-CertificatePath",
        application.certificate_path,
        "-Url",
        application.tenant_url,
        "-PasswordEnv",
        # THE NAME, NEVER THE PASSWORD. A credential in `argv` is in
        # the process list for every account on this machine and in
        # the shell history afterwards. The child reads the variable
        # itself; this process never holds the value.
        application.certificate_password_env,
    ]

    try:
        finished = runner(argv)
    except FileNotFoundError as missing:
        raise Unavailable(
            "pwsh is not on this machine. The Graph slices mint their token "
            "through the same PowerShell the other collectors use, so that one "
            "application registration serves both."
        ) from missing
    except subprocess.TimeoutExpired as slow:
        raise Unavailable(
            f"the sign-in did not finish within {timeout} seconds. An "
            "application with a certificate needs nobody at a keyboard, so a "
            "wait this long is a network or a directory that did not answer."
        ) from slow

    token = finished.stdout.strip().splitlines()[-1:] or [""]
    token = token[0].strip()

    if finished.returncode != 0 or not token:
        # THE CHILD'S OWN WORDS, AND NOT A CODE. `certificate not found`,
        # `AADSTS700027` and `application not consented` are three different
        # problems with three different answers, and a caller told only that
        # authentication failed has to guess which.
        detail = (finished.stderr or finished.stdout or "").strip()
        raise Unavailable(
            "the application did not authenticate against this directory.\n\n"
            + _redacted(detail)
        )

    if token.count(".") != 2:
        raise Unavailable(
            "PowerShell returned something that is not a bearer token. Nothing "
            "was spent: this refuses rather than sending an unknown string to "
            "Microsoft Graph."
        )
    return token


def _subprocess(timeout: int) -> Runner:
    """The real runner. Kept behind the parameter so the default is testable
    by substitution rather than by monkey-patching a module attribute."""

    def run(argv: list[str]) -> Any:
        return subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )

    return run


def _redacted(detail: str) -> str:
    """A failure message with anything token-shaped removed.

    A refusal is printed, logged and pasted into an issue. A message that
    quoted the credential it failed with would publish it in the one place a
    person is most likely to copy.
    """
    return "\n".join(
        "<a value that looked like a token was removed from this message>"
        if part.count(".") == 2 and len(part) > 100
        else part
        for line in detail.splitlines()
        for part in [line]
    )
