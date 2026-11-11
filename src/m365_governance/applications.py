"""Application registrations and their credentials, read from Microsoft Graph.

WHAT THIS IS FOR. Which applications are registered in the directory, what
credentials each holds and when each credential ends, and what each one asks
to be allowed to do. It is the dataset behind a question an operator asks
every month: which secrets and certificates are about to stop working, and
which have already.

WHAT IT DELIBERATELY LEAVES OUT.

- A SECRET IS NEVER HERE, AND NEITHER IS ITS HINT. Microsoft Graph does not
  return a secret's value after it is created, and it does return `hint`, the
  first characters of it. The hint is dropped before anything is written: a
  fragment of a credential has no use in evidence and one obvious misuse.
- A certificate's bytes (`key`) are not requested and its thumbprint is not
  kept. When it ends is the fact; which certificate it is, is the operator's
  to look up by the application's id.
- Owners are not read. Who is responsible for an application is a different
  read with a different answer about people.

WHAT AN APPLICATION ASKS FOR IS NOT WHAT IT WAS GIVEN. `requiredResourceAccess`
is the request written on the registration. Whether an administrator or a user
consented to any of it is recorded on the service principal and in the grants,
which this does not read: it needs `Directory.Read.All`, the widest read this
engine has considered, and that is a separate decision.

Source: `GET /applications`, Microsoft Graph v1.0. Least privilege as the
reference records it: `Application.Read.All`
(docs/ENTRA-COLLECTOR-PERMISSIONS.md). Checked 11 November 2026.

TENANT-VERIFICATION-PENDING. Contract-tested against a stand-in transport. It
has not read a directory, and the proof registry holds no record of it.
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

NAME = "applications"
AREA = "applications"

SELECT = (
    "id",
    "appId",
    "displayName",
    "createdDateTime",
    "signInAudience",
    "passwordCredentials",
    "keyCredentials",
    "requiredResourceAccess",
)

PATH = f"applications?$select={','.join(SELECT)}&$top=999"

REQUESTED = [AREA]

ORIGIN = Origin(
    collector="graph-applications",
    collector_version="1.0.0",
    workload="entra",
    source_system="Microsoft Entra ID",
)

ADDRESSABLE = {
    "app_id": "appId",
    "sign_in_audience": "signInAudience",
    "created_at": "createdDateTime",
}

#: What is kept of one credential. Nothing that is, or is part of, a secret.
KEPT = ("startDateTime", "endDateTime")


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


def _credentials(item: dict[str, Any]) -> dict[str, Any]:
    """The credentials of one application, as when each starts and ends.

    AN ABSENT LIST IS NOT AN EMPTY ONE. An application with no secret
    publishes an empty array; a response that does not carry the property at
    all did not say. The first is zero credentials, observed. The second is
    missing, and a reader counting expiring secrets must not read it as none.
    """
    out: dict[str, Any] = {}
    kept: list[dict[str, Any]] = []
    whole = True
    for name, prop, kind in (
        ("secrets", "passwordCredentials", "secret"),
        ("certificates", "keyCredentials", "certificate"),
    ):
        value = item.get(prop)
        if not isinstance(value, list):
            whole = False
            out[name] = {
                "state": "missing",
                "detail": f"`{prop}` was not present on the application returned.",
            }
            continue
        out[name] = {
            "state": "observed",
            "value": len(value),
            "raw": {"field": prop, "value": len(value)},
        }
        for credential in value:
            if isinstance(credential, dict):
                kept.append(
                    {
                        "kind": kind,
                        "starts_at": credential.get(KEPT[0]),
                        "ends_at": credential.get(KEPT[1]),
                    }
                )
    kept.sort(key=lambda c: (str(c["ends_at"] or ""), c["kind"]))
    if whole:
        out["credentials"] = {"state": "observed", "value": kept}
        ends = sorted(str(c["ends_at"]) for c in kept if c["ends_at"])
        if ends:
            out["earliest_credential_end"] = {"state": "observed", "value": ends[0]}
    else:
        out["credentials"] = {
            "state": "missing",
            "detail": "One kind of credential was not returned, so the list "
            "would be incomplete and is not published.",
        }
    return out


def _requests(item: dict[str, Any]) -> dict[str, Any]:
    """What the registration asks for, counted by kind. A request, not a grant."""
    value = item.get("requiredResourceAccess")
    if not isinstance(value, list):
        return {
            "requested_application_permissions": {
                "state": "missing",
                "detail": "`requiredResourceAccess` was not returned.",
            },
            "requested_delegated_permissions": {
                "state": "missing",
                "detail": "`requiredResourceAccess` was not returned.",
            },
        }
    kinds = [
        access.get("type")
        for resource in value
        if isinstance(resource, dict)
        for access in (resource.get("resourceAccess") or [])
        if isinstance(access, dict)
    ]
    return {
        "requested_application_permissions": {
            "state": "observed",
            "value": kinds.count("Role"),
        },
        "requested_delegated_permissions": {
            "state": "observed",
            "value": kinds.count("Scope"),
        },
    }


def collect(reader: GraphReader, tenant_url: str, observed_at: str) -> Collected:
    """Read every application the service returns, page after page."""
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

    applications = [item for item in read.items if item.get("id")]
    population: dict[str, Any] = {
        "population": {"state": "observed", "value": "entra-application-registrations"},
        "acquisition_method": {"state": "observed", "value": "enumerated"},
    }
    if read.unavailable is None:
        population["count"] = {
            "state": "observed",
            "value": len(applications),
            "raw": {"field": "GET /applications", "value": len(applications)},
        }
    else:
        population["count"] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": (
                f"{len(applications)} applications were read before the read "
                f"ended: {read.unavailable.detail} That is a lower bound and "
                "not the number of applications."
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
    for item in applications:
        outcome.documents.append(
            graph_slice.document(
                reader,
                host,
                observed_at,
                coverage,
                ORIGIN,
                resource_type="application",
                native_id=str(item["id"]),
                display_name=str(item.get("displayName") or item["id"]),
                facts={
                    "application": {
                        **graph_slice.addressable(
                            ADDRESSABLE, item, of="application registration"
                        ),
                        **_credentials(item),
                        **_requests(item),
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
