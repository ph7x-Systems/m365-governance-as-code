"""Collecting the access-policy surface, and concluding nothing about it.

One slice and one session: the Conditional Access policies, the named locations
they reference, and the Security Defaults state. The authentication strength a
policy requires is a fourth question with no fourth request — it arrives inside
`grantControls.authenticationStrength`, which the source audit established
before any of this was written.

**IT COLLECTS AND DOES NOT INTERPRET.** No threshold, no score, no opinion
about whether a tenant's access policy is good. A policy is carried whole, in
the shape Microsoft sent it, because a projection chosen here decides in advance
what a future rule may read and leaves the reader no way back to what the tenant
said.

**A DENIAL IS EVIDENCE AND IS WRITTEN DOWN.** An area that could not be read
produces a document about the tenant saying so, with the state and the reason.
Writing nothing would leave a directory that looks like a tenant with no
Conditional Access at all, which is the one conclusion this slice must never
allow anybody to reach by accident.

WHAT AN UNRESOLVED REFERENCE STAYS. A policy names users, groups, roles and
applications by directory id, and this slice does not go looking for their
display names: resolving them would be directory-wide inventory, which is
outside this question, and a friendly label the collector had to fetch is a
bigger claim than an id it was handed. The ids travel exactly as they arrived.
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

#: The collections this slice reads, by the area name that reaches `coverage`.
#: These names are the vocabulary a reader sees when something was not read, so
#: they are the product's words rather than the API's paths.
AREAS = {
    "conditional-access-policies": "identity/conditionalAccess/policies",
    "named-locations": "identity/conditionalAccess/namedLocations",
}

#: Read as a single resource rather than a collection. Security Defaults is one
#: object; wrapping it in a list of one keeps every consumer reading one shape.
SINGLE = {
    "security-defaults": "policies/identitySecurityDefaultsEnforcementPolicy",
}

#: Every area this slice sets out to read, which is what `requested` means. It
#: is fixed rather than derived from what succeeded: a run that was denied
#: everything still asked for all three.
REQUESTED = sorted([*AREAS, *SINGLE])

#: The name this slice answers to on the command line.
NAME = "conditional-access"

COLLECTOR = "graph-conditional-access"
COLLECTOR_VERSION = "1.0.0"
WORKLOAD = "entra"

ORIGIN = Origin(
    collector=COLLECTOR,
    collector_version=COLLECTOR_VERSION,
    workload=WORKLOAD,
    source_system="Microsoft Entra ID",
)

#: Which resource type each area produces.
TYPES = {
    "conditional-access-policies": "conditional-access-policy",
    "named-locations": "named-location",
    "security-defaults": "security-defaults-policy",
}

#: How an unreadable area is named in `coverage.unavailable`, written once
#: for every Graph slice.
COVERAGE_STATE = graph_slice.COVERAGE_STATE


@dataclass
class Collected:
    """What one run of this slice produced, area by area."""

    documents: list[dict[str, Any]] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    unavailable: dict[str, dict[str, str]] = field(default_factory=dict)

    #: The areas that were asked for, whatever happened to them.
    requested: list[str] = field(default_factory=lambda: list(REQUESTED))

    @property
    def complete(self) -> bool:
        return not self.unavailable


def collect(reader: GraphReader, *, tenant_url: str, observed_at: str) -> Collected:
    """Read every area, keeping each one's outcome separate.

    **One area failing never removes another's result and never turns the run
    into a failure.** A tenant whose policies read and whose named locations
    were denied produced evidence worth the policies, and the coverage says
    which half is missing and why.

    The areas are read first and the documents built afterwards, so that every
    document carries the coverage of the whole run. A document that carried only
    its own area would leave the manifest unable to report an area that produced
    no documents at all, which is exactly the area a reader most needs told
    about.
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
            "state": COVERAGE_STATE.get(read.unavailable.state, read.unavailable.state),
            "detail": read.unavailable.detail,
        }

    outcome.completed.sort()
    # ONE NAME PER AREA, AND IT USED TO BE TWO. Coverage said
    # `conditional-access-policies` and the facts said
    # `conditional_access_policies`, so anything joining the two -- which is
    # anything asking WHICH AREA a conclusion came from -- matched nothing, and
    # Conditional Access reported evidence collected and no conclusions while
    # three rules were deciding on it. The facts key is the name, because that
    # is what a rule addresses.
    coverage = {
        "requested": [_key(area) for area in outcome.requested],
        "completed": [_key(area) for area in outcome.completed],
        "unavailable": {
            _key(area): entry for area, entry in outcome.unavailable.items()
        },
    }

    for area, read in reads:
        if read.unavailable is not None:
            outcome.documents.append(
                _refusal(area, read, reader, host, observed_at, coverage)
            )
            continue
        for item in read.items:
            outcome.documents.append(
                _observation(area, item, reader, host, observed_at, coverage)
            )

    return outcome


def _observation(
    area: str,
    item: dict[str, Any],
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """One resource, as the evidence contract carries it.

    The value is the object Microsoft sent, unaltered. Nothing is renamed,
    flattened or dropped: a field this engine does not understand today is a
    field a rule may need tomorrow, and a collector that removed it would have
    answered a narrower question than the one it was asked.

    AND THAT PRINCIPLE HAD A CONSEQUENCE NOBODY NAMED: NO RULE COULD READ IT.
    An evidence path addresses `family.fact` and reads that fact's value, so
    `conditional_access_policies.state` resolved to the FACT's state -- the
    word `observed` -- and never to the policy's. The family collected against
    a real directory for weeks and carried zero rules, and the reason was not
    that nobody had written one. It was that nobody could.

    So the object stays whole and the fields a rule needs are published BESIDE
    it, each naming the property it came from. Two ways to read the same
    observation, and neither is a second copy: one is the vendor's bytes, the
    other is this engine saying which of them it is prepared to answer about.
    """
    native = str(item.get("id") or "").strip() or f"{area}-without-an-id"
    # NESTED UNDER THE FAMILY, LIKE EVERY OTHER COLLECTOR. The addressable
    # fields were published at the top level -- `policy_state` beside
    # `conditional_access_policies` -- and every other collector in this engine
    # publishes `permissions.unique_scope_count`, `items.count`,
    # `forwarding.remote_domains`. The difference was invisible until something
    # asked which AREA a conclusion came from: a flat `policy_state` belongs to
    # no family, so Conditional Access reported evidence collected and no
    # conclusions while two rules were deciding on it.
    family = _key(area)
    fields: dict[str, Any] = {}
    fields.update(_addressable(area, item))
    # NESTED OBJECTS ARE FLATTENED ONE LEVEL, and only where a rule asked. A
    # policy's user scope lives at `conditions.users` and its controls at
    # `grantControls`, so a rule addressing `included_users` would otherwise
    # need a path grammar this engine does not have.
    fields.update(
        _addressable(
            f"{area}:conditions",
            ((item.get("conditions") or {}).get("users") or {}),
        )
    )
    fields.update(_addressable(f"{area}:grant", (item.get("grantControls") or {})))
    fields.update(_exclusion_count(item))

    # A FAMILY IS A GROUP OF FACTS, NOT A FACT WITH FACTS INSIDE IT. The
    # evidence contract says so and every other collector obeys it:
    # `permissions` holds `unique_scope_count` and carries no value of its own.
    # The untouched Graph object is a fact named `policy` inside the family,
    # which is where a reader looks for it and where the schema allows it.
    facts: dict[str, Any] = {
        family: {"policy": {"state": "observed", "value": item}, **fields}
    }

    return _document(
        reader,
        host,
        observed_at,
        coverage,
        resource_type=TYPES[area],
        native_id=native,
        display_name=str(item.get("displayName") or native),
        facts=facts,
    )


#: What a rule may address, per area, as `fact name -> the property it reads`.
#:
#: DELIBERATELY SHORT. A field arrives here when a rule needs it, so that the
#: list is a record of what this engine will answer about rather than a second
#: copy of the Graph shape drifting beside the first.
ADDRESSABLE: dict[str, dict[str, str]] = {
    "conditional-access-policies": {
        "policy_state": "state",
        "policy_name": "displayName",
    },
    # The condition and grant fields a rule needs, flattened from the nested
    # objects Graph returns. They arrive here because a rule needed them, which
    # is what keeps this list a record of what the engine answers about rather
    # than a second copy of the Graph shape drifting beside the first.
    "conditional-access-policies:conditions": {
        "included_users": "includeUsers",
        "excluded_users": "excludeUsers",
        "excluded_groups": "excludeGroups",
        "excluded_roles": "excludeRoles",
    },
    "conditional-access-policies:grant": {
        "grant_operator": "operator",
        "built_in_controls": "builtInControls",
        "authentication_strength": "authenticationStrength",
    },
    "named-locations": {
        "location_name": "displayName",
        "is_trusted": "isTrusted",
    },
}


def _addressable(area: str, item: dict[str, Any]) -> dict[str, Any]:
    """The fields of one object, as facts a rule can name.

    The rule that absent is not false lives in `graph_slice.addressable`, which
    every Graph slice uses. What stays here is which fields this slice answers
    about and what kind of thing they belong to.
    """
    return graph_slice.addressable(
        ADDRESSABLE.get(area, {}),
        item,
        of=TYPES.get(area.split(":", 1)[0], area),
    )


def _refusal(
    area: str,
    read: Read,
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """An area that could not be read, as a fact about the tenant."""
    return graph_slice.refusal(area, read, reader, host, observed_at, coverage, ORIGIN)


def _document(
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
    *,
    resource_type: str,
    native_id: str,
    display_name: str,
    facts: dict[str, Any],
    scope: str = "collection",
    parent: dict[str, str] | None = None,
) -> dict[str, Any]:
    return graph_slice.document(
        reader,
        host,
        observed_at,
        coverage,
        ORIGIN,
        resource_type=resource_type,
        native_id=native_id,
        display_name=display_name,
        facts=facts,
        scope=scope,
        parent=parent,
    )


def _key(area: str) -> str:
    """The area name as a facts key, which rules read by name."""
    return graph_slice.key(area)


def write(collected: Collected, directory: Path) -> list[Path]:
    """Write one document per resource, into the directory the caller chose."""
    return graph_slice.write(collected.documents, directory)


def _safe(name: str) -> str:
    """A filename from an identifier this engine does not get to reshape."""
    return graph_slice.safe(name)


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
    """Collect the slice and write its account of itself beside the evidence."""
    return graph_slice.run(
        name=NAME,
        collect=lambda reader, tenant, observed_at: collect(
            reader, tenant_url=tenant, observed_at=observed_at
        ),
        token=token,
        output=output,
        tenant_url=tenant_url,
        client_id=client_id,
        endpoint=endpoint,
        transport=transport,
        on_progress=on_progress,
    )


def _exclusion_count(item: dict[str, Any]) -> dict[str, Any]:
    """How many users, groups and roles a policy excludes, added up.

    THE PATH GRAMMAR HAS NO WAY TO SAY `THIS ARRAY IS EMPTY`. `not-exists`
    tests whether a fact is present, and a policy that excludes nobody
    publishes three arrays that are present and empty, so a rule written
    against absence passes on exactly the case it exists to catch.

    A count is a fact about the policy rather than a judgement about it: it
    adds three numbers the vendor returned and names all three in its raw
    provenance. It covers the three lists together because a policy excluding
    one group and no users has a recovery path, and a rule reading only
    `excludeUsers` would have missed it.
    """
    users = (item.get("conditions") or {}).get("users") or {}
    fields = ("excludeUsers", "excludeGroups", "excludeRoles")
    present = [name for name in fields if isinstance(users.get(name), list)]
    if not present:
        return {
            "exclusions_declared": {
                "state": "missing",
                "detail": (
                    "None of `excludeUsers`, `excludeGroups` or `excludeRoles` "
                    "was returned as a list, so how many principals this policy "
                    "excludes was not established. Absent is not zero: zero is a "
                    "policy that excludes nobody, and this is a reading that did "
                    "not happen."
                ),
            }
        }
    total = sum(len(users.get(name) or []) for name in present)
    return {
        "exclusions_declared": {
            "state": "observed",
            "value": total,
            "raw": {
                "field": ", ".join(present),
                "value": {name: users.get(name) for name in present},
            },
        }
    }
