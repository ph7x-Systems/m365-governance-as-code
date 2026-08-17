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

from . import registry
from .collecting import COLLECTOR, _now, _run

#: What the collector prints when the session is open, and the only line this
#: module reads out of the stream. Prefixed because PnP.PowerShell prints on
#: the way — including a device code somebody has to read off the screen — and
#: picking the answer out of that by shape rather than by name would eventually
#: pick the wrong line.
ESTABLISHED = re.compile(r"^CONNECTION (\{.*\})\s*$")

#: What the collector prints for the OTHER question, before any sign-in.
#:
#: TWO QUESTIONS, AND ONE FIELD WOULD ANSWER NEITHER WELL. Which directory owns
#: an address is answerable from public OpenID discovery, by anybody, without a
#: token — measured, not assumed. Which directory a session is operating in is
#: only answerable by the session. A GUID the whole world can obtain without
#: reaching the tenant is not evidence that a collection looked at that tenant,
#: and putting both in one field would make a lookup indistinguishable from an
#: observation.
RESOLVED = re.compile(r"^RESOLVED (\{.*\})\s*$")


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


#: The suffix Microsoft documents for the admin centre, which is the only label
#: that differs between the two hosts of one tenant.
ADMIN = "-admin"


def tenant_host(url: str) -> str:
    """The tenant's host, from any of its addresses.

    The admin centre lives on a different host from the sites it administers,
    and Microsoft documents the format as `https://{prefix}-admin.sharepoint.com`
    with the same shape in every cloud, so only the first label differs and
    removing the suffix is a documented mapping rather than a guess.

    <https://learn.microsoft.com/sharepoint/dev/spfx/set-up-your-developer-tenant>

    WHY IT EXISTS TWICE. The SharePoint collector normalises its own host inside
    PowerShell, in the process that holds the session; this is the same
    documented mapping applied in the process that reads Microsoft Graph. Both
    cite the mapping rather than each other, and a tenant reached through the
    admin centre by one and through Graph by the other has to come out as one
    organisation or an assessment cannot assemble them.

    KNOWN LIMIT, RECORDED RATHER THAN PAPERED OVER. In multi-geo, a satellite
    lives on its own host and this returns the satellite. The mapping above is
    documented only for the admin centre.
    """
    host = url.strip()
    for prefix in ("https://", "http://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix) :]
    host = host.split("/")[0].split("?")[0].strip().rstrip(".")
    labels = host.split(".")
    if labels[0].lower().endswith(ADMIN):
        labels[0] = labels[0][: -len(ADMIN)]
    return ".".join(labels)


@dataclass
class Connection:
    """What one attempt to reach a tenant turned out to be."""

    reach: Reach
    returncode: int
    seconds: float
    attempted_at: str

    #: What was asked: the addresses and the application registration.
    requested: dict[str, Any] = field(default_factory=dict)

    #: Which directory owns the address, from public discovery. Present even
    #: when the sign-in failed, because resolving an address needs no session.
    address: dict[str, Any] = field(default_factory=dict)

    #: What the session said about itself. Empty unless `reach` is established.
    established: dict[str, Any] = field(default_factory=dict)

    #: Every line the collector printed, in order. Carried whole because the
    #: device code, the consent prompt and the failure all arrive here.
    output: list[str] = field(default_factory=list)

    because: list[str] = field(default_factory=list)

    @property
    def host(self) -> str | None:
        """The address that answered. NOT the identity of the organisation."""
        return self.established.get("host") or self.address.get("host")

    @property
    def resolved_tenant_id(self) -> str | None:
        """Which directory owns the address. Authoritative, and not observed.

        From public discovery, so it is true of the address and says nothing
        about which directory a session operated in. It is what lets two hosts
        of one organisation be proven to be one, and it is not evidence that
        anybody reached either of them.
        """
        return self.address.get("resolved_tenant_id")

    @property
    def observed_tenant_id(self) -> str | None:
        """Which directory the session operated in. None until a session says.

        Null today: nothing reads it from the session yet, and the resolved
        value may not stand in for it. The two answer different questions.
        """
        return self.established.get("observed_tenant_id")

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
    established = _one(lines, ESTABLISHED)
    address = _one(lines, RESOLVED)

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
        address=address,
        established=established,
        output=lines,
        because=_because(reach, returncode, cancelled, established, lines),
    )


def _one(lines: list[str], pattern: re.Pattern[str]) -> dict[str, Any]:
    """The one line matching, parsed. Empty when there is not exactly one."""
    found = [m.group(1) for m in (pattern.match(line) for line in lines) if m]
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


def document(connection: Connection) -> dict[str, Any]:
    """The connection as the contract it declares.

    IT IS A CONTRACT NOW, HAVING BEEN ARGUED NOT TO BE. The first version
    published this shape and called it deliberately unversioned, because a
    session ends when the process does and so has nothing to persist. That
    answered the wrong question: persistence is not the test, DEPENDENCE is. A
    consumer already parses this to decide whether a collection may start, and
    a shape somebody depends on is a contract whether or not it is called one —
    the only difference being whether it can change without anybody noticing.
    """
    session = connection.established
    return {
        "$schema": registry.contract("connection"),
        "reach": str(connection.reach),
        "attempted_at": connection.attempted_at,
        "seconds": round(connection.seconds, 3),
        "exit_code": connection.returncode,
        "requested": {
            "site_url": connection.requested.get("site_url"),
            "tenant_url": connection.requested.get("tenant_url"),
            "client_id": connection.requested.get("client_id", ""),
            "device_login": bool(connection.requested.get("device_login")),
        },
        "address": {
            # None, not "", when nothing was resolved. A collector that never
            # ran read no address, and echoing back the one that was asked for
            # would put a request where a reader expects a result.
            "host": connection.address.get("host"),
            "resolved_tenant_id": connection.address.get("resolved_tenant_id"),
            "how": "public-discovery",
            "detail": connection.address.get("detail"),
        },
        # Null rather than an empty object when nothing opened. An empty session
        # would read as one that established nothing, which is a different and
        # much weaker statement than there being no session at all.
        "session": {
            "host": session.get("host", ""),
            "client_id": session.get("client_id", ""),
            "identity_kind": session.get("identity_kind", "not-established"),
            "connection_type": session.get("connection_type", ""),
            "scopes": list(session.get("scopes") or []),
            # NEVER `resolved_tenant_id`. That one is a lookup anybody can
            # perform without reaching this tenant, and copying it here would
            # make a public resolution indistinguishable from an observation, in
            # the one field a reader trusts to mean what was seen.
            "observed_tenant_id": session.get("observed_tenant_id"),
        }
        if session
        else None,
        "because": connection.because,
    }


def describe(connection: Connection) -> str:
    """The report a person reads. Two questions, kept apart on the page.

    THE LAYOUT IS THE POINT. Address resolution and the authenticated session
    are printed as separate blocks because they are separate claims, and a
    reader who saw one GUID under one heading would reasonably conclude that
    the session had been observed in that directory. It has not.
    """
    out = [f"{connection.reach.upper()}  after {connection.seconds:.1f}s", ""]

    out.append("Address resolution")
    if connection.resolved_tenant_id:
        out += [
            f"  {connection.address.get('host')}",
            f"  owned by  {connection.resolved_tenant_id}",
            "",
            "  Public discovery, and no session was involved. Authoritative for",
            "  the address: two hosts that resolve here to one directory ARE one",
            "  organisation. It says nothing about who signed in.",
        ]
    else:
        detail = connection.address.get("detail") or "the address was not resolved"
        out.append(f"  not resolved: {detail}")

    out += ["", "Authenticated session"]
    if connection.reach is Reach.ESTABLISHED:
        out += [
            f"  identity   {connection.identity}",
            f"  observed   {connection.observed_tenant_id or 'not established'}",
            f"  client id  {connection.established.get('client_id')}",
            f"  connection {connection.established.get('connection_type')}",
        ]
        scopes = connection.established.get("scopes") or []
        if scopes:
            out.append(f"  scopes     {', '.join(sorted(scopes))}")
        out += [
            "",
            "  WHICH DIRECTORY THIS SESSION OPERATED IN IS NOT ESTABLISHED, and",
            "  the resolved id above does not stand in for it: that one is a",
            "  lookup anybody can perform without reaching this tenant.",
        ]
    else:
        out.append("  none. Nothing was collected and nothing was written.")

    out += ["", "Because:"]
    out += [f"  {reason}" for reason in connection.because]
    return "\n".join(out) + "\n"
