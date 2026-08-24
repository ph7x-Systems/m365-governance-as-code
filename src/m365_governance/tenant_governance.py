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
    # `$select` AND NOT `$expand`, AND THE REASON IS NOT PERFORMANCE.
    #
    # This first read `$expand=principal`, which returns each assignment with
    # the account attached: display name, user principal name, object id. The
    # collector counted them and dropped the rest, so nothing was published --
    # and an administrator roster had still crossed the network, sat in this
    # process's memory and passed through whatever logs and proxies are between
    # here and Microsoft, in order to be discarded.
    #
    # Not receiving it is a stronger property than not publishing it, and it is
    # available for the asking. Microsoft also documents the expansion as thin:
    # the principal on a role assignment supports `$select` nested in `$expand`
    # FOR ID ONLY, so the property this slice actually needs was never reliably
    # coming through it anyway.
    "global-administrators": (
        "roleManagement/directory/roleAssignments"
        f"?$filter=roleDefinitionId eq '{GLOBAL_ADMINISTRATOR}'"
        "&$select=id,principalId,directoryScopeId"
    ),
}

#: How one principal is asked whether it is synchronised. Two fields, and the
#: identifier is one the caller already had: nothing here can return a name.
PRINCIPAL = "users/{id}?$select=id,onPremisesSyncEnabled"

#: Read as a single resource rather than a collection.
SINGLE = {
    "authorization-policy": "policies/authorizationPolicy",
    # THE METHOD CONFIGURATIONS ARRIVE WITHOUT BEING ASKED FOR. Microsoft
    # documents `authenticationMethodConfigurations` as automatically expanded
    # on this GET, so there is no `$expand` here and no second call: one read
    # returns the policy and the state of every method in it.
    "authentication-methods-policy": "policies/authenticationMethodsPolicy",
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
    "authentication-methods-policy": "authentication-methods-policy",
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
    "authentication-methods-policy": {
        # WHICH POLICY THE TENANT IS ACTUALLY GOVERNED BY. The same document
        # means three different things depending on this one value: the policy
        # may be used for authentication only with the legacy MFA and SSPR
        # policies still respected, for both with the legacy ones still
        # respected, or for both with the legacy ones ignored. A rule that
        # reads a method's state without reading this has read a value out of
        # the context that decides whether it is in force.
        "policy_migration_state": "policyMigrationState",
    },
}

#: The methods this engine will answer about, by the identifier Microsoft gives
#: each configuration.
#:
#: A SUBSET, AND ON PURPOSE. A method arrives here when a rule needs it, so the
#: list stays a record of what this engine answers rather than a second copy of
#: Microsoft's method catalogue drifting beside the first. The two here are the
#: two the vendor has published a dated end for.
METHODS = {
    "sms": "Sms",
    "voice": "Voice",
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
        facts = {family: _privileged_summary(read.items, reader)}
        display = "Global Administrator assignments"
    elif area == "authentication-methods-policy":
        item = read.items[0] if read.items else {}
        facts = {
            family: {
                "policy": {"state": "observed", "value": item},
                **graph_slice.addressable(
                    ADDRESSABLE[area], item, of="authentication methods policy"
                ),
                **_method_states(item),
            }
        }
        display = "Authentication methods policy"
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


def _method_states(item: dict[str, Any]) -> dict[str, Any]:
    """Whether each method this engine answers about is enabled, as a flat fact.

    THE PATH GRAMMAR ADDRESSES `family.fact` AND CANNOT REACH INTO A LIST. The
    states arrive as a collection of configurations, each identified by its own
    `id`, so a rule written against the collection would have nothing to name.
    One fact per method, flattened here, is what makes the question askable.

    ABSENT IS NOT DISABLED, and here that distinction has teeth. Microsoft
    expands every configuration on this read, so a method missing from the
    response is not a method that is off: it is a response this engine did not
    get what it expected from. Writing `disabled` would turn a collector's bad
    day into a tenant's clean result, which is the failure this engine exists
    to remove -- and it would do it on the read that decides whether the
    tenant's second factor can be intercepted.
    """
    configurations = item.get("authenticationMethodConfigurations")
    if not isinstance(configurations, list):
        return {
            f"method_{name}": {
                "state": "missing",
                "detail": (
                    "`authenticationMethodConfigurations` was not returned as a "
                    "list. Microsoft documents it as automatically expanded on "
                    "this read, so its absence is a reading that did not "
                    f"happen rather than {identifier} being disabled."
                ),
            }
            for name, identifier in METHODS.items()
        }

    by_id = {
        c.get("id"): c for c in configurations if isinstance(c, dict) and c.get("id")
    }
    out: dict[str, Any] = {}
    for name, identifier in METHODS.items():
        configuration = by_id.get(identifier)
        if configuration is None or "state" not in configuration:
            out[f"method_{name}"] = {
                "state": "missing",
                "detail": (
                    f"no configuration identified as `{identifier}` carried a "
                    "`state` in what Microsoft returned. Absent is not "
                    "disabled: the method's state was not established."
                ),
            }
            continue
        out[f"method_{name}"] = {
            "state": "observed",
            "value": configuration["state"],
            "raw": {
                "field": f"authenticationMethodConfigurations[{identifier}].state",
                "value": configuration["state"],
            },
        }
    return out


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


def _privileged_summary(
    items: list[dict[str, Any]], reader: GraphReader
) -> dict[str, Any]:
    """Role assignments counted, with no name ever received.

    ONE SMALL READ PER PRINCIPAL, AND NOT ONE LARGE ONE. Asking the directory
    for each account by the identifier the assignment already gave, selecting
    two fields, is more requests than expanding the relationship and is the
    only shape in which a display name never arrives. The cost is bounded by
    the number of people holding the most privileged role in the tenant, and a
    tenant where that number makes this slow has already been told so by the
    rule that counts them.

    A PRINCIPAL THAT IS NOT A USER ANSWERS `404`, and that is how a service
    principal is told from a person without asking what either is called. The
    reader calls a `404` `not-supported`, which is right for its own purpose --
    a surface this cloud does not serve -- and here means the object is not in
    `users`. The local reading is written down rather than pushed into the
    reader, whose general mapping is correct as it stands.

    FOUR COUNTS AND NOT THREE. A principal the directory would not answer
    about is neither cloud-only nor synchronised: it is a reading that did not
    happen, and folding it into either count would let a rule conclude from
    evidence nobody collected. Microsoft documents `onPremisesSyncEnabled` as
    `true` when the object is synced from an on-premises directory, so
    anything else that was actually returned is not currently synced.
    """
    users = 0
    others = 0
    synced = 0
    established = 0

    for principal in sorted(
        {str(item.get("principalId") or "") for item in items} - {""}
    ):
        read = reader.one(PRINCIPAL.format(id=principal))
        if read.unavailable is not None:
            if read.unavailable.state == "not-supported":
                # Not in `users`: a service principal, a group, or an object
                # this directory no longer holds. Not a person either way.
                others += 1
            continue
        users += 1
        account = read.items[0] if read.items else {}
        if "onPremisesSyncEnabled" not in account:
            continue
        established += 1
        if account["onPremisesSyncEnabled"] is True:
            synced += 1

    def observed(value: int, field_name: str) -> dict[str, Any]:
        return {
            "state": "observed",
            "value": value,
            # THE RAW PROVENANCE IS THE COUNT, NOT THE ROWS. Every other fact in
            # this engine carries what it read; this one carries what it counted
            # and how, because carrying the rows is carrying the roster -- and
            # in this shape the rows were never received to carry.
            "raw": {"field": field_name, "value": value},
        }

    return {
        "assignments": observed(len(items), "roleAssignments (count)"),
        "user_assignments": observed(users, "principals answering in users (count)"),
        "service_principal_assignments": observed(
            others, "principals not answering in users (count)"
        ),
        "synced_from_on_premises": observed(
            synced, "onPremisesSyncEnabled true (count)"
        ),
        "cloud_only": observed(
            established - synced, "onPremisesSyncEnabled returned and not true (count)"
        ),
        "principals_not_established": observed(
            users - established, "onPremisesSyncEnabled not returned (count)"
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
