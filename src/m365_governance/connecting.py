"""Reaching a tenant, and saying what was established. Nothing is collected.

`doctor` answers whether this installation is sound. Nothing answered the other
half: whether the application registration in front of you can reach the tenant
in front of you, and as whom. Finding that out by starting a collection means
finding it out several minutes in, from a failure that looks like a tenant
problem rather than a consent problem.

**A connection is not an observation about a resource.** It writes no evidence
and produces no document, and it is deliberately not a contract: what it
reports is the state of a session that ends when the process does.

WHAT IT DOES NOT ESTABLISH, AND THIS IS THE POINT. Which directory the tenant
belongs to. A host is an address; the identity is the directory id, and no
collection path for it is proven on a real tenant. A documented candidate
exists and is recorded in docs/COLLECTION-PATH-AUDIT.md as
`needs-tenant-validation`. Until a run settles it, connecting tells you the
address answered and who answered for it, and `identity` stays
`not-established` — which is a real answer about identity rather than a gap.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .collecting import COLLECTOR, _now, _run

#: What the collector prints when the session is open, and the only line this
#: module reads out of the stream. Prefixed because PnP.PowerShell prints on
#: the way — including a device code somebody has to read off the screen — and
#: picking the answer out of that by shape rather than by name would eventually
#: pick the wrong line.
ESTABLISHED = re.compile(r"^CONNECTION (\{.*\})\s*$")


class Reach(StrEnum):
    """How the attempt to reach a tenant ended.

    Four words rather than a boolean, for the same reason a collection has
    four: `refused` and `unreachable` are different sentences to a person
    holding an application registration, and collapsing them sends somebody to
    check their network when the answer was consent.
    """

    ESTABLISHED = "established"
    """A session opened, and it says who it belongs to."""

    REFUSED = "refused"
    """The tenant answered and would not have us: consent, or the wrong tenant."""

    UNREACHABLE = "unreachable"
    """Nothing answered, or the local environment cannot try."""

    CANCELLED = "cancelled"
    """Stopped deliberately. Never inferred from an exit code."""


@dataclass
class Connection:
    """What one attempt to reach a tenant turned out to be."""

    reach: Reach
    returncode: int
    seconds: float
    attempted_at: str

    #: What was asked: the addresses and the application registration.
    requested: dict[str, Any] = field(default_factory=dict)

    #: What the session said about itself. Empty unless `reach` is established.
    established: dict[str, Any] = field(default_factory=dict)

    #: Every line the collector printed, in order. Carried whole because the
    #: device code, the consent prompt and the failure all arrive here.
    output: list[str] = field(default_factory=list)

    because: list[str] = field(default_factory=list)

    @property
    def host(self) -> str | None:
        """The address that answered. NOT the identity of the organisation."""
        return self.established.get("host")

    @property
    def identity(self) -> str:
        """Which kind of identity looked, in the evidence contract's vocabulary.

        `not-established` while nothing has read the directory id, which is
        today. A delegated session is what both interactive and device sign-in
        produce, and that is a fact about the flow rather than about which
        organisation this is.
        """
        return self.established.get("identity_kind", "not-established")


def connect(
    *,
    client_id: str,
    site_url: str | None = None,
    tenant_url: str | None = None,
    device_login: bool = False,
    on_progress: Callable[[str], None] | None = None,
    engine: Callable[..., tuple[int, str, str, bool]] | None = None,
) -> Connection:
    """Open a read-only session, and report what it turned out to be.

    `on_progress` receives each line as it is printed, and it is not optional in
    practice: a device-code sign-in prints a code somebody has to read off the
    screen and type elsewhere, so a caller that buffered the output would be
    asking a person to wait for a code that had already been shown.
    """
    argv = [
        "pwsh",
        "-NoProfile",
        "-File",
        str(COLLECTOR),
        "-Mode",
        "Connect",
        "-ClientId",
        client_id,
    ]
    if site_url:
        argv += ["-SiteUrl", site_url]
    if tenant_url:
        argv += ["-TenantUrl", tenant_url]
    if device_login:
        argv.append("-DeviceLogin")

    attempted_at = _now()
    started = time.monotonic()
    run = engine or _run
    returncode, out, _err, cancelled = run(argv, on_progress)
    elapsed = time.monotonic() - started

    lines = out.splitlines()
    established = _established(lines)

    if cancelled:
        reach = Reach.CANCELLED
    elif established:
        reach = Reach.ESTABLISHED
    elif returncode != 0:
        # The tenant answering "no" and nothing answering at all are different
        # sentences to somebody holding an app registration. The collector
        # having run at all is what separates them: a refusal comes back
        # through the process, and an unreachable host or a missing pwsh does
        # not get that far.
        reach = Reach.REFUSED if lines else Reach.UNREACHABLE
    else:
        # Exited zero and said nothing. Not established: something answered and
        # this engine did not understand it, which is not the same as a session.
        reach = Reach.UNREACHABLE

    return Connection(
        reach=reach,
        returncode=returncode,
        seconds=elapsed,
        attempted_at=attempted_at,
        requested={
            "site_url": site_url,
            "tenant_url": tenant_url,
            "client_id": client_id,
            "device_login": device_login,
        },
        established=established,
        output=lines,
        because=_because(reach, returncode, cancelled, established, lines),
    )


def _established(lines: list[str]) -> dict[str, Any]:
    """The connection line, parsed. Empty when there is not exactly one."""
    found = [m.group(1) for m in (ESTABLISHED.match(line) for line in lines) if m]
    if len(found) != 1:
        return {}
    try:
        parsed = json.loads(found[0])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _because(
    reach: Reach,
    returncode: int,
    cancelled: bool,
    established: dict[str, Any],
    lines: list[str],
) -> list[str]:
    """Why the reach is what it is. Never empty."""
    reasons: list[str] = []
    if cancelled:
        reasons.append("the caller stopped the sign-in")
    if reach is Reach.ESTABLISHED:
        reasons.append(f"a delegated session opened against {established.get('url')}")
        scopes = established.get("scopes") or []
        reasons.append(
            f"{len(scopes)} scopes granted" if scopes else "no scopes were reported"
        )
        reasons.append(
            "the directory identity was not read: no collection path for it is "
            "proven on a tenant, so this says which address answered and not "
            "which organisation it belongs to"
        )
    else:
        if returncode != 0 and not cancelled:
            reasons.append(f"the collector exited {returncode}")
        if not lines:
            reasons.append("the collector printed nothing at all")
        elif not established:
            reasons.append("no session was reported")
        # The last thing it said is usually the reason, and it is the
        # collector's own words rather than ours.
        tail = [line for line in lines if line.strip()][-3:]
        reasons.extend(tail)
    return reasons


def describe(connection: Connection) -> str:
    """The report a person reads. One screen, and no invented certainty."""
    out = [f"{connection.reach.upper()}  after {connection.seconds:.1f}s", ""]

    if connection.reach is Reach.ESTABLISHED:
        out += [
            f"  host       {connection.host}",
            f"  identity   {connection.identity}",
            f"  client id  {connection.established.get('client_id')}",
            f"  connection {connection.established.get('connection_type')}",
        ]
        scopes = connection.established.get("scopes") or []
        if scopes:
            out.append(f"  scopes     {', '.join(sorted(scopes))}")
        out += [
            "",
            "  The organisation this address belongs to is NOT established.",
            "  A host is an endpoint; the identity is the directory id, and no",
            "  collection path for it is proven on a tenant yet.",
        ]
    else:
        out.append("  nothing was collected and nothing was written.")

    out += ["", "Because:"]
    out += [f"  {reason}" for reason in connection.because]
    return "\n".join(out) + "\n"
