"""The directory's own settings, read from Microsoft Graph.

WHAT THIS SLICE IS FOR. The catalogue this engine carries grew twenty-one rules
about SharePoint and five about everything else, and the reason was never that
Microsoft documents less about the rest of Microsoft 365. It was that the rest
was not being collected. This reads two surfaces that decide what every user in
a tenant may do and who may do anything at all, and neither of them is a site.

**IT PUBLISHES COUNTS OF PEOPLE AND NEVER PEOPLE.** The privileged-role area
reads role assignments, which arrive carrying the principal they were made to:
a display name, a user principal name, an object id. None of that reaches the
evidence. What a rule needs to decide is how many there are and how many of
them are cloud-only, and a collector that wrote the rest would put a directory's
administrator roster into every report, every archive and every copy of a report
somebody forwarded. The aggregate is the whole document, and it is one document
about the tenant rather than one per assignment for the same reason.

WHAT IT DELIBERATELY DOES NOT READ. Eligible assignments under Privileged
Identity Management live on another surface with another licence behind it. A
tenant using PIM properly can hold one permanent Global Administrator and eight
eligible ones, and this slice sees the one. That is a limitation carried by
every rule that reads these facts, written there rather than repaired by
quietly reading a surface that may not answer.
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

#: The role whose assignments this counts, by the template identifier Microsoft
#: publishes for it. A name would be wrong in every tenant whose directory is
#: not in English, and the template id is the same everywhere.
GLOBAL_ADMINISTRATOR = "62e90394-69f5-4237-9190-012177145e10"

#: The collections this slice reads, by the area name that reaches `coverage`.
AREAS = {
    "global-administrators": (
        "roleManagement/directory/roleAssignments"
        f"?$filter=roleDefinitionId eq '{GLOBAL_ADMINISTRATOR}'&$expand=principal"
    ),
}

#: Read as a single resource rather than a collection.
SINGLE = {
    "authorization-policy": "policies/authorizationPolicy",
}

REQUESTED = sorted([*AREAS, *SINGLE])

NAME = "tenant-governance"

ORIGIN = Origin(
    collector="graph-tenant-governance",
    collector_version="1.0.0",
    workload="entra",
    source_system="Microsoft Entra ID",
)

#: Which resource type each area produces.
TYPES = {
    "global-administrators": "privileged-role-summary",
    "authorization-policy": "authorization-policy",
}

#: What a rule may address, per area, as `fact name -> the property it reads`.
#:
#: DELIBERATELY SHORT. A field arrives here when a rule needs it, so that the
#: list is a record of what this engine will answer about rather than a second
#: copy of the Graph shape drifting beside the first.
ADDRESSABLE: dict[str, dict[str, str]] = {
    "authorization-policy": {
        "guest_invitations_from": "allowInvitesFrom",
        "user_consent_for_risky_apps": "allowUserConsentForRiskyApps",
        "email_verified_users_may_join": "allowEmailVerifiedUsersToJoinOrganization",
        "msol_powershell_blocked": "blockMsolPowerShell",
        "guest_role_template_id": "guestUserRoleId",
    },
    # Flattened one level from `defaultUserRolePermissions`, because the
    # evidence path grammar addresses `family.fact` and has no way to reach
    # inside a value.
    "authorization-policy:default-user-role": {
        "users_may_create_apps": "allowedToCreateApps",
        "users_may_create_security_groups": "allowedToCreateSecurityGroups",
        "users_may_create_tenants": "allowedToCreateTenants",
        "users_may_read_other_users": "allowedToReadOtherUsers",
        "users_may_read_own_bitlocker_keys": "allowedToReadBitlockerKeysForOwnedDevice",
    },
}


@dataclass
class Collected:
    """What one run of this slice produced, area by area."""

    documents: list[dict[str, Any]] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    unavailable: dict[str, dict[str, str]] = field(default_factory=dict)
    requested: list[str] = field(default_factory=lambda: list(REQUESTED))

    @property
    def complete(self) -> bool:
        return not self.unavailable


def collect(reader: GraphReader, tenant_url: str, observed_at: str) -> Collected:
    """Read every area, keeping each one's outcome separate.

    One area failing never removes another's result and never turns the run
    into a failure. The areas are read first and the documents built afterwards,
    so that every document carries the coverage of the whole run.
    """
    host = tenant_host(tenant_url)
    outcome = Collected()

    reads: list[tuple[str, Read]] = [
        *((area, reader.read(path)) for area, path in AREAS.items()),
        *((area, reader.one(path)) for area, path in SINGLE.items()),
    ]

    for area, read in reads:
        if read.unavailable is None:
            outcome.completed.append(area)
            continue
        outcome.unavailable[area] = {
            "state": graph_slice.coverage_state(read.unavailable.state),
            "detail": read.unavailable.detail,
        }

    coverage = {
        "requested": [graph_slice.key(area) for area in outcome.requested],
        "completed": [graph_slice.key(area) for area in outcome.completed],
        "unavailable": {
            graph_slice.key(area): reason
            for area, reason in outcome.unavailable.items()
        },
    }

    for area, read in reads:
        if read.unavailable is not None:
            outcome.documents.append(
                graph_slice.refusal(
                    area, read, reader, host, observed_at, coverage, ORIGIN
                )
            )
            continue
        outcome.documents.append(
            _document_for(area, read, reader, host, observed_at, coverage)
        )

    return outcome


def _document_for(
    area: str,
    read: Read,
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """One document per AREA, and never one per principal.

    Both areas here describe the tenant rather than a resource inside it, which
    is why neither produces a document per item. For the authorization policy
    that is arithmetic -- it is a singleton. For the role assignments it is the
    point: the answer is how many, and the principals are dropped before
    anything is written.
    """
    family = graph_slice.key(area)
    if area == "global-administrators":
        facts = {family: _privileged_summary(read.items)}
        display = "Global Administrator assignments"
    else:
        item = read.items[0] if read.items else {}
        facts = {
            family: {
                # The object Microsoft sent, unaltered, beside the fields this
                # engine is prepared to answer about. A field this engine does
                # not understand today is a field a rule may need tomorrow.
                "policy": {"state": "observed", "value": item},
                **graph_slice.addressable(
                    ADDRESSABLE[area], item, of="authorization policy"
                ),
                **graph_slice.addressable(
                    ADDRESSABLE[f"{area}:default-user-role"],
                    (item.get("defaultUserRolePermissions") or {}),
                    of="default user role permission set",
                ),
                **_consent_policies(item),
            }
        }
        display = "Authorization policy"

    return graph_slice.document(
        reader,
        host,
        observed_at,
        coverage,
        ORIGIN,
        resource_type=TYPES[area],
        native_id=host,
        display_name=display,
        facts=facts,
        scope="tenant",
    )


def _consent_policies(item: dict[str, Any]) -> dict[str, Any]:
    """How many app consent policies the default user role is assigned.

    Microsoft states what the empty case means -- "An empty list indicates user
    consent to apps is disabled" -- so the count is a fact with a documented
    reading, and absent is not zero.
    """
    return graph_slice.counted(
        "user_consent_policies_assigned",
        (item.get("defaultUserRolePermissions") or {}),
        "permissionGrantPoliciesAssigned",
        absent=(
            "`permissionGrantPoliciesAssigned` was not returned as a list, so "
            "whether users may consent to applications was not established. "
            "Absent is not an empty list: an empty list is Microsoft's "
            "documented way of saying user consent is disabled, and this is a "
            "reading that did not happen."
        ),
    )


def _privileged_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Role assignments counted, with every principal discarded.

    THREE COUNTS AND NOT TWO. A principal whose `onPremisesSyncEnabled` was not
    returned is neither cloud-only nor synced: it is a reading that did not
    happen, and folding it into either count would let a rule conclude from
    evidence nobody collected. Microsoft documents the property as `true` when
    the object is synced from an on-premises directory, so anything else that
    was actually returned is not currently synced.
    """
    users = [
        item
        for item in items
        if "user" in str((item.get("principal") or {}).get("@odata.type", "")).lower()
    ]
    principals = [item.get("principal") or {} for item in users]
    synced = [p for p in principals if p.get("onPremisesSyncEnabled") is True]
    established = [p for p in principals if "onPremisesSyncEnabled" in p]

    def observed(value: int, field_name: str) -> dict[str, Any]:
        return {
            "state": "observed",
            "value": value,
            # THE RAW PROVENANCE IS THE COUNT, NOT THE ROWS. Every other fact in
            # this engine carries what it read; this one carries what it counted
            # and how, because carrying the rows is carrying the roster.
            "raw": {"field": field_name, "value": value},
        }

    return {
        "assignments": observed(len(items), "roleAssignments (count)"),
        "user_assignments": observed(len(users), "principal @odata.type user (count)"),
        "service_principal_assignments": observed(
            len(items) - len(users), "principal not a user (count)"
        ),
        "synced_from_on_premises": observed(
            len(synced), "principal.onPremisesSyncEnabled true (count)"
        ),
        "cloud_only": observed(
            len(established) - len(synced),
            "principal.onPremisesSyncEnabled returned and not true (count)",
        ),
        "principals_not_established": observed(
            len(principals) - len(established),
            "principal.onPremisesSyncEnabled not returned (count)",
        ),
        "role_definition_id": {
            "state": "observed",
            "value": GLOBAL_ADMINISTRATOR,
            "raw": {"field": "roleDefinitionId", "value": GLOBAL_ADMINISTRATOR},
        },
    }


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
