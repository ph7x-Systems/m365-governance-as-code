"""Service principals, read from Microsoft Graph.

WHAT THIS IS FOR. An application registration is the definition; a service
principal is that application present in a directory, and it is the object
that signs in and is granted things. A directory holds service principals for
its own registrations and for applications that belong to other
organisations, which is where the question of who was let in is answered.
This collects each one with whether it is enabled, which organisation owns
the application behind it, and the credentials the service principal itself
holds.

THE JOIN THIS MAKES POSSIBLE. `app_id` is the same value on a registration
and on its service principal, so the two collections relate on it: a
registration with no service principal cannot sign in to this directory, and
a service principal with no registration here belongs to somebody else.

WHAT IT DELIBERATELY LEAVES OUT. A secret is never here, and neither is its
hint, nor a certificate's bytes or thumbprint: the same rule as the
applications collector, for the same reason. What a service principal was
GRANTED is not read: delegated grants need `Directory.Read.All`, which has
not been decided, and this does not read application role assignments.

Source: `GET /servicePrincipals`, Microsoft Graph v1.0, under
`Application.Read.All`. Checked 12 November 2026.

Contract-tested against a stand-in transport, and read from a directory
once, on 12 November 2026: the proof registry holds that record and what it
did not cover.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import collecting, graph_slice
from .applications import _credentials
from .connecting import tenant_host
from .graph import GLOBAL, GraphReader, Transport
from .graph_slice import HOW, TOKEN_VARIABLE, Origin  # noqa: F401  (re-exported)

NAME = "service-principals"
AREA = "service_principals"

SELECT = (
    "id",
    "appId",
    "displayName",
    "servicePrincipalType",
    "accountEnabled",
    "appOwnerOrganizationId",
    "passwordCredentials",
    "keyCredentials",
)

PATH = f"servicePrincipals?$select={','.join(SELECT)}&$top=999"

REQUESTED = [AREA]

ORIGIN = Origin(
    collector="graph-service-principals",
    collector_version="1.0.0",
    workload="entra",
    source_system="Microsoft Entra ID",
)

ADDRESSABLE = {
    "app_id": "appId",
    "kind": "servicePrincipalType",
    "account_enabled": "accountEnabled",
    "owner_organisation_id": "appOwnerOrganizationId",
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


def _ownership(item: dict[str, Any], directory: str | None) -> dict[str, Any]:
    """Whether the application behind this belongs to the directory it is in.

    Decided from two identifiers and never from a name: the organisation the
    service says owns the application, and the directory the token was issued
    in. When either is not known the answer is that it is not established.
    """
    owner = item.get("appOwnerOrganizationId")
    if not owner or not directory:
        return {
            "state": "missing",
            "detail": "The owning organisation or this directory's identifier "
            "was not available, so the two could not be compared.",
        }
    return {"state": "observed", "value": str(owner).lower() == directory.lower()}


def collect(reader: GraphReader, tenant_url: str, observed_at: str) -> Collected:
    """Read every service principal the service returns, page after page."""
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
    principals = [item for item in read.items if item.get("id")]
    population: dict[str, Any] = {
        "population": {"state": "observed", "value": "entra-service-principals"},
        "acquisition_method": {"state": "observed", "value": "enumerated"},
    }
    if read.unavailable is None:
        population["count"] = {"state": "observed", "value": len(principals)}
    else:
        population["count"] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": (
                f"{len(principals)} service principals were read before the "
                f"read ended: {read.unavailable.detail} That is a lower bound."
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
    directory = reader.identity.observed_tenant_id
    for item in principals:
        outcome.documents.append(
            graph_slice.document(
                reader,
                host,
                observed_at,
                coverage,
                ORIGIN,
                resource_type="service-principal",
                native_id=str(item["id"]),
                display_name=str(item.get("displayName") or item["id"]),
                facts={
                    "service_principal": {
                        **graph_slice.addressable(
                            ADDRESSABLE, item, of="service principal"
                        ),
                        "owned_by_this_directory": _ownership(item, directory),
                        **_credentials(item),
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
