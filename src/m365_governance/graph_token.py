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

import os
import re
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
# EVERY INPUT FROM THE ENVIRONMENT, AND NO `param()` BLOCK.
#
# This took its inputs as named parameters and was invoked with `-Command`,
# which evaluates the text and never binds what follows it. So every value
# arrived null and PnP reported the first null it refuses: `Cannot bind
# argument to parameter 'Tenant'` -- a message about the directory, produced by
# a working certificate against a working directory. No graph slice could
# collect from any tenant.
#
# `-File` would bind them, and this module is forbidden to write ANY file: a
# token it keeps outlives the authorization it was granted under, and the test
# enforcing that scans this source for the calls that write, rather than
# trusting intent. The environment costs nothing, binds reliably, and keeps
# every value out of the process list -- which is what the password already
# did, for the same reason.
$ClientId = $env:PH7X_GRAPH_CLIENT_ID
$TenantId = $env:PH7X_GRAPH_TENANT_ID
$CertificatePath = $env:PH7X_GRAPH_CERTIFICATE
$Url = $env:PH7X_GRAPH_URL
$PasswordEnv = $env:PH7X_GRAPH_PASSWORD_ENV
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


def environment_for(application: Application) -> dict[str, str]:
    """What the child is told, as a value a test can read.

    A function rather than a literal inside `acquire`, because the property
    that matters here -- the password travels as the NAME of a variable and
    never as the password -- was asserted against `argv` while the values were
    parameters, and had nothing to read once they stopped being parameters. It
    is asserted against this instead, which is the thing that decides it.
    """
    return {
        "PH7X_GRAPH_CLIENT_ID": application.client_id,
        "PH7X_GRAPH_TENANT_ID": application.tenant_id,
        "PH7X_GRAPH_CERTIFICATE": application.certificate_path,
        "PH7X_GRAPH_URL": application.tenant_url,
        # THE NAME, NEVER THE PASSWORD. The child looks the variable up itself;
        # this process never holds the value, and it is not in the process list
        # for every account on this machine.
        "PH7X_GRAPH_PASSWORD_ENV": application.certificate_password_env,
    }


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

    argv = ["pwsh", "-NoProfile", "-NonInteractive", "-Command", SCRIPT]
    environment = environment_for(application)
    # THE ENVIRONMENT BELONGS TO THE RUNNER, NOT TO THE CALL. A second
    # positional argument would have changed the contract every substituted
    # runner in the tests is written against, to carry something no double
    # needs. It is closed over here instead, so `Runner` stays `argv -> result`.
    runner = run if run is not None else _subprocess(timeout, environment)

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


#: The delegated script. The same rules as the one above: every input from
#: the environment, the token and nothing else on standard output, no file.
DELEGATED_SCRIPT = """
$ClientId = $env:PH7X_GRAPH_CLIENT_ID
$Url = $env:PH7X_GRAPH_URL
$Scopes = @($env:PH7X_GRAPH_SCOPES -split ' ' | Where-Object { $_ })
$ErrorActionPreference = 'Stop'
Import-Module PnP.PowerShell -ErrorAction Stop
if ($env:PH7X_GRAPH_DEVICE_LOGIN -eq '1') {
    Connect-PnPOnline -Url $Url -DeviceLogin -ClientId $ClientId
}
else {
    Connect-PnPOnline -Url $Url -Interactive -ClientId $ClientId
}
Get-PnPAccessToken -ResourceTypeName Graph -Scopes $Scopes
"""


def acquire_delegated(
    *,
    client_id: str,
    tenant_url: str,
    scopes: tuple[str, ...],
    device_login: bool = False,
    timeout: int = 300,
    run: Runner | None = None,
) -> str:
    """One delegated Graph token, as the person who signs in, for these scopes.

    THIS REACHES A DIRECTORY, exactly as `acquire` does, and as a person. It
    signs in through the same library and the same application registration
    the SharePoint collectors use, so a session kept by `login` answers
    without asking and anybody else is asked to sign in.

    ONLY THE SCOPES THE COLLECTOR DECLARES ARE ASKED FOR. They are the ones
    recorded beside the collector, never a wider set kept for convenience. A
    scope nobody has consented to makes the directory ask for consent at the
    sign-in, and that is the person's decision to take there: this function
    grants nothing and consents to nothing.

    The token is returned to a caller that spends it at once. It is not
    written, cached or placed in an argument.
    """
    if not client_id or not tenant_url:
        raise Unavailable(
            "a delegated Graph token needs the application registration and "
            "the tenant address: --client-id and --tenant-url, a project "
            "file, or a connection kept by `login`."
        )
    if not scopes or "not-established" in scopes:
        raise Unavailable(
            "this collector records no Microsoft Graph scope to ask for, and "
            "a token is never requested for a scope nobody named."
        )
    environment = {
        "PH7X_GRAPH_CLIENT_ID": client_id,
        "PH7X_GRAPH_URL": tenant_url,
        "PH7X_GRAPH_SCOPES": " ".join(scopes),
        "PH7X_GRAPH_DEVICE_LOGIN": "1" if device_login else "",
    }
    argv = ["pwsh", "-NoProfile", "-Command", DELEGATED_SCRIPT]
    runner = run if run is not None else _subprocess(timeout, environment)
    try:
        finished = runner(argv)
    except FileNotFoundError as missing:
        raise Unavailable("pwsh is not on this machine.") from missing
    except subprocess.TimeoutExpired as slow:
        raise Unavailable(
            f"the sign-in did not finish within {timeout} seconds. Nobody "
            "completed it in the browser, or the directory did not answer."
        ) from slow

    token = (finished.stdout.strip().splitlines()[-1:] or [""])[0].strip()
    if finished.returncode != 0 or not token:
        detail = (finished.stderr or finished.stdout or "").strip()
        raise Unavailable(
            "no delegated token was issued for "
            + ", ".join(scopes)
            + ". The sign-in was not completed, or consent to a scope was not "
            "given.\n\n" + _redacted(detail)
        )
    if token.count(".") != 2:
        raise Unavailable(
            "PowerShell returned something that is not a bearer token. Nothing "
            "was spent."
        )
    return token


def _subprocess(timeout: int, environment: dict[str, str] | None = None) -> Runner:
    """The real runner. Kept behind the parameter so the default is testable
    by substitution rather than by monkey-patching a module attribute."""

    def run(argv: list[str]) -> Any:
        return subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, **(environment or {})},
        )

    return run


#: Three base64url segments, the first starting as every JSON header does.
_TOKEN_SHAPED = re.compile(
    r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"
)


def _redacted(detail: str) -> str:
    """A failure message with anything token-shaped removed.

    A refusal is printed, logged and pasted into an issue. A message that
    quoted the credential it failed with would publish it in the one place a
    person is most likely to copy.
    """
    removed = "<a value that looked like a token was removed from this message>"
    # A WHOLE LINE THAT IS A TOKEN, AND A TOKEN INSIDE A SENTENCE. The first
    # rule only caught a token alone on its line; a library that wrote
    # `failed with <token>` passed it straight through.
    lines = [
        removed if line.count(".") == 2 and len(line) > 100 else line
        for line in detail.splitlines()
    ]
    return _TOKEN_SHAPED.sub(removed, "\n".join(lines))
