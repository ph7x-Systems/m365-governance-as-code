"""Guest accounts in the directory, read from Microsoft Graph.

WHAT THIS IS FOR. A composed scenario about access from outside the
organisation needs to know which identities are guests, by an identifier that
does not change. That is what this collects: one document per guest account,
keyed by the directory's own object id, and one document for the tenant that
carries how many were read.

WHAT IT DELIBERATELY LEAVES OUT. No display name, no mail address, no user
principal name and no invited address is requested: `$select` names six
properties and none of them says who anybody is. A name is a person, an
inventory of guests does not need one to be joined to anything, and evidence
that never held a name cannot leak one. Somebody who needs the name has the
object id and their own directory.

A GUEST EXISTING IS NOT A GUEST HAVING ACCESS. This says an account of type
Guest is in the directory, whether it is enabled and whether its invitation
was accepted. It says nothing about what the account can reach.

Source: `GET /users` with `$filter=userType eq 'Guest'`, Microsoft Graph v1.0.
Least privilege as the reference records it: `User.Read.All`
(docs/ENTRA-COLLECTOR-PERMISSIONS.md). Checked 11 November 2026.

Contract-tested against a stand-in transport, and read from a directory
once, on 11 November 2026: the proof registry holds that record and what it
did not cover.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import collecting, graph_slice
from .connecting import tenant_host
from .graph import GLOBAL, GraphReader, Transport
from .graph_slice import HOW, TOKEN_VARIABLE, Origin  # noqa: F401  (re-exported)

NAME = "guests"
AREA = "guests"

#: The six properties asked for. None of them identifies a person.
SELECT = (
    "id",
    "userType",
    "accountEnabled",
    "externalUserState",
    "externalUserStateChangeDateTime",
    "createdDateTime",
)

PATH = f"users?$filter=userType eq 'Guest'&$select={','.join(SELECT)}&$top=999"

REQUESTED = [AREA]

ORIGIN = Origin(
    collector="graph-guests",
    collector_version="1.0.0",
    workload="entra",
    source_system="Microsoft Entra ID",
)

#: What a reader may address about one guest, as `fact name -> property`.
ADDRESSABLE = {
    "user_type": "userType",
    "account_enabled": "accountEnabled",
    "invitation_state": "externalUserState",
    "invitation_state_changed_at": "externalUserStateChangeDateTime",
    "created_at": "createdDateTime",
}


@dataclass
class Collected:
    """What one run of this slice produced."""

    documents: list[dict[str, Any]] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    unavailable: dict[str, dict[str, str]] = field(default_factory=dict)
    requested: list[str] = field(default_factory=lambda: list(REQUESTED))

    @property
    def complete(self) -> bool:
        return not self.unavailable


def collect(reader: GraphReader, tenant_url: str, observed_at: str) -> Collected:
    """Read every guest the service returns, page after page.

    WHAT WAS READ BEFORE A REFUSAL IS KEPT, AND THE COUNT IS NOT. A read that
    stopped part of the way wrote real accounts and those documents stand. The
    number of them is not the number of guests, so the tenant document
    carries the state the read ended in and no count: a count there would be a
    lower bound printed as a total.
    """
    host = tenant_host(tenant_url)
    outcome = Collected()
    read = reader.read(PATH)

    if read.unavailable is None:
        outcome.completed.append(AREA)
    else:
        outcome.unavailable[AREA] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": read.unavailable.detail,
        }
    coverage = {
        "requested": list(outcome.requested),
        "completed": list(outcome.completed),
        "unavailable": dict(outcome.unavailable),
    }

    # ONLY WHAT THE SERVICE CALLED A GUEST. The filter is the service's, and a
    # service that ignored it would hand back every account in the directory.
    # An object whose type is not Guest is not written as one.
    guests = [item for item in read.items if item.get("userType") == "Guest"]
    foreign = len(read.items) - len(guests)

    population: dict[str, Any] = {
        "population": {"state": "observed", "value": "entra-guest-user-accounts"},
        "acquisition_method": {"state": "observed", "value": "enumerated"},
    }
    if read.unavailable is None and not foreign:
        population["count"] = {
            "state": "observed",
            "value": len(guests),
            "raw": {"field": "GET /users (userType eq 'Guest')", "value": len(guests)},
        }
    elif read.unavailable is not None:
        population["count"] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": (
                f"{len(guests)} guest accounts were read before the read "
                f"ended: {read.unavailable.detail} That is a lower bound and "
                "not the number of guests."
            ),
        }
    else:
        population["count"] = {
            "state": "missing",
            "detail": (
                f"The service returned {foreign} accounts that are not guests "
                "to a request filtered to guests, so the filter cannot be "
                "trusted to have returned every guest either."
            ),
        }

    outcome.documents.append(
        graph_slice.document(
            reader,
            host,
            observed_at,
            coverage,
            ORIGIN,
            resource_type="tenant",
            native_id=host,
            display_name=host,
            facts={AREA: population},
            scope="tenant",
            parent=None,
        )
    )
    for item in guests:
        identifier = str(item.get("id") or "")
        if not identifier:
            continue
        outcome.documents.append(
            graph_slice.document(
                reader,
                host,
                observed_at,
                coverage,
                ORIGIN,
                resource_type="user",
                native_id=identifier,
                # The object id and never a name: see the module's own account
                # of what is left out.
                display_name=identifier,
                facts={
                    "guest": graph_slice.addressable(
                        ADDRESSABLE, item, of="user account"
                    )
                },
            )
        )
    return outcome


def write(collected: Collected, directory: Path) -> list[Path]:
    return graph_slice.write(collected.documents, directory)


def run(
    *,
    token: str,
    output: Path,
    tenant_url: str,
    client_id: str = "",
    endpoint: str = GLOBAL,
    transport: Transport | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> collecting.Outcome:
    return graph_slice.run(
        name=NAME,
        collect=collect,
        token=token,
        output=output,
        tenant_url=tenant_url,
        client_id=client_id,
        endpoint=endpoint,
        transport=transport,
        on_progress=on_progress,
    )
