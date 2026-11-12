"""Microsoft 365 groups, their owners and their members, read from Microsoft Graph.

WHAT THIS IS FOR. A site connected to a Microsoft 365 group is administered
through that group, and a team is that group again. Who answers for such a
workspace is the group's owners, and that is a different list from the site's
administrators. This collects, for every Microsoft 365 group, how many owners
and how many members it has, by the kind of object each is.

COUNTS BY KIND, AND NO IDENTITY. For owners and members only `id` is asked
for, and the service adds the kind of each object. Neither is written: what
is kept is how many users and how many other objects. A name is a person,
and a count joins to a site as well as a list of names does.

THE GROUP'S OWN NAME IS KEPT. A group is a workspace, not a person, and an
operator who is told that a workspace has one owner needs to know which.

WHAT A COUNT OF OWNERS DOES NOT SAY. An owner being listed is not somebody
being responsible: the account may be disabled or belong to somebody who left,
and neither is read here. Owners of groups created in Exchange, distribution
groups and groups synchronised from on-premises are not available from this
surface at all, which is why only Microsoft 365 groups are asked for.

Source: `GET /groups` filtered to Microsoft 365 groups, then
`GET /groups/{id}/owners` and `GET /groups/{id}/members`, Microsoft Graph
v1.0. Least privilege as the reference records it: `GroupMember.Read.All`,
which lists groups and reads owners and memberships. Checked 12 November 2026.

Contract-tested against a stand-in transport. It has not read a directory,
and the proof registry holds no record of it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import collecting, graph_slice
from .connecting import tenant_host
from .graph import GLOBAL, GraphReader, Read, Transport
from .graph_slice import HOW, TOKEN_VARIABLE, Origin  # noqa: F401  (re-exported)

NAME = "groups"
AREA = "groups"

SELECT = (
    "id",
    "displayName",
    "createdDateTime",
    "visibility",
    "resourceProvisioningOptions",
)

PATH = (
    "groups?$filter=groupTypes/any(c:c eq 'Unified')"
    f"&$select={','.join(SELECT)}&$top=999"
)
OWNERS = "groups/{id}/owners?$select=id&$top=999"
MEMBERS = "groups/{id}/members?$select=id&$top=999"

REQUESTED = [AREA]

ORIGIN = Origin(
    collector="graph-groups",
    collector_version="1.0.0",
    workload="entra",
    source_system="Microsoft Entra ID",
)

ADDRESSABLE = {"created_at": "createdDateTime", "visibility": "visibility"}

USER = "#microsoft.graph.user"


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


def _counted(read: Read, what: str) -> dict[str, Any]:
    """How many of a relationship were returned, by kind, or why not.

    A READ THAT ENDED EARLY PUBLISHES NO COUNT. Two owners read before a
    refusal is at least two owners, and a workspace reported as having two
    when it has five is a wrong answer about who is responsible.
    """
    if read.unavailable is not None:
        state = graph_slice.coverage_state(read.unavailable.state)
        absent = {
            "state": state,
            "detail": f"{len(read.items)} {what} were read before the read "
            f"ended: {read.unavailable.detail}",
        }
        return {what: absent, f"user_{what}": dict(absent)}
    users = sum(1 for item in read.items if item.get("@odata.type") == USER)
    return {
        what: {"state": "observed", "value": len(read.items)},
        f"user_{what}": {"state": "observed", "value": users},
    }


def collect(reader: GraphReader, tenant_url: str, observed_at: str) -> Collected:
    """Every Microsoft 365 group, then its owners and its members."""
    host = tenant_host(tenant_url)
    outcome = Collected()
    read = reader.read(PATH)

    groups = [item for item in read.items if item.get("id")]
    relations = {
        str(item["id"]): (
            reader.read(OWNERS.format(id=item["id"])),
            reader.read(MEMBERS.format(id=item["id"])),
        )
        for item in groups
    }
    refused = sum(
        1
        for owners, members in relations.values()
        if owners.unavailable is not None or members.unavailable is not None
    )

    if read.unavailable is None and not refused:
        outcome.completed.append(AREA)
    elif read.unavailable is not None:
        outcome.unavailable[AREA] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": read.unavailable.detail,
        }
    else:
        outcome.unavailable[AREA] = {
            "state": "partial",
            "detail": f"{refused} of {len(groups)} groups did not return their "
            "owners or their members. Each says so in its own document.",
        }
    coverage = {
        "requested": list(outcome.requested),
        "completed": list(outcome.completed),
        "unavailable": dict(outcome.unavailable),
    }

    population: dict[str, Any] = {
        "population": {"state": "observed", "value": "entra-microsoft-365-groups"},
        "acquisition_method": {"state": "observed", "value": "enumerated"},
    }
    if read.unavailable is None:
        population["count"] = {"state": "observed", "value": len(groups)}
    else:
        population["count"] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": (
                f"{len(groups)} groups were read before the read ended: "
                f"{read.unavailable.detail} That is a lower bound and not the "
                "number of groups."
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
    for item in groups:
        identifier = str(item["id"])
        owners, members = relations[identifier]
        options = item.get("resourceProvisioningOptions")
        team = (
            {"state": "observed", "value": "Team" in options}
            if isinstance(options, list)
            else {
                "state": "missing",
                "detail": "`resourceProvisioningOptions` was not returned.",
            }
        )
        outcome.documents.append(
            graph_slice.document(
                reader,
                host,
                observed_at,
                coverage,
                ORIGIN,
                resource_type="group",
                native_id=identifier,
                display_name=str(item.get("displayName") or identifier),
                facts={
                    "group": {
                        **graph_slice.addressable(
                            ADDRESSABLE, item, of="Microsoft 365 group"
                        ),
                        "is_team": team,
                        **_counted(owners, "owners"),
                        **_counted(members, "members"),
                    }
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
