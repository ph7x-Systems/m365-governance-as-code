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

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import collecting, registry
from .connecting import tenant_host
from .graph import GLOBAL, GraphReader, Read, Refused, Transport

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

#: Which resource type each area produces.
TYPES = {
    "conditional-access-policies": "conditional-access-policy",
    "named-locations": "named-location",
    "security-defaults": "security-defaults-policy",
}

#: How an unreadable area is named in `coverage.unavailable`, whose vocabulary
#: is four words and does not include `invalid`.
#:
#: RECORDED, NOT SMUGGLED. A `200` carrying something that is not readable as
#: Graph is `invalid` to the reader and has no word of its own in the evidence
#: contract, so it lands on `missing` — nobody read it — with the reader's own
#: sentence kept intact. The gap is written up in the slice audit beside the
#: `401` one rather than resolved by choosing the nearest available word and
#: saying nothing.
COVERAGE_STATE = {"invalid": "missing"}


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
    coverage = {
        "requested": outcome.requested,
        "completed": outcome.completed,
        "unavailable": outcome.unavailable,
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
    """
    native = str(item.get("id") or "").strip() or f"{area}-without-an-id"
    return _document(
        reader,
        host,
        observed_at,
        coverage,
        resource_type=TYPES[area],
        native_id=native,
        display_name=str(item.get("displayName") or native),
        facts={_key(area): {"state": "observed", "value": item}},
    )


def _refusal(
    area: str,
    read: Read,
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """An area that could not be read, as a fact about the tenant.

    THIS DOCUMENT IS THE POINT OF THE SLICE. Without it a denied read leaves the
    same directory as a tenant that genuinely has no Conditional Access, and a
    rule over that evidence would pass. With it the rule sees a fact whose state
    is not `observed` and answers `unknown`, which is the honest answer and the
    one nobody can act on by mistake.
    """
    assert read.unavailable is not None
    state = COVERAGE_STATE.get(read.unavailable.state, read.unavailable.state)
    return _document(
        reader,
        host,
        observed_at,
        coverage,
        resource_type="tenant",
        native_id=host,
        display_name=host,
        facts={_key(area): {"state": state, "detail": read.unavailable.detail}},
        scope="tenant",
        parent=None,
    )


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
    tenant = {
        # From the token's own `tid` claim, and from nowhere else. Public
        # discovery answers which directory owns an address, which anybody can
        # ask without reaching the tenant; this field means the directory a
        # session was actually opened in, and the two never share a field.
        "id": reader.identity.observed_tenant_id,
        "host": host,
    }
    if parent is None and resource_type != "tenant":
        parent = {"workload": WORKLOAD, "type": "tenant", "native_id": host}

    return {
        "$schema": registry.contract("evidence"),
        "provenance": {
            "collected_at": observed_at,
            "collector": COLLECTOR,
            "collector_version": COLLECTOR_VERSION,
            "source_system": "Microsoft Entra ID",
            "source_api": reader.source_api,
            # Read from the token rather than taken from the arguments. A caller
            # cannot tell this engine which kind of identity it holds.
            "identity_kind": reader.identity.kind,
            "scopes": list(reader.identity.scopes),
            "acquisition": "collected",
            "tenant": dict(tenant),
        },
        "coverage": json.loads(json.dumps(coverage)),
        "resource": {
            "workload": WORKLOAD,
            "type": resource_type,
            "native_id": native_id,
            "tenant": dict(tenant),
            "scope": scope,
            "parent": parent,
            "display_name": display_name,
        },
        "facts": facts,
    }


def _key(area: str) -> str:
    """The area name as a facts key, which rules read by name."""
    return area.replace("-", "_")


def write(collected: Collected, directory: Path) -> list[Path]:
    """Write one document per resource, into the directory the caller chose.

    The filename carries the resource type and its native id. Two areas that
    each refuse produce two documents about the same tenant, so the area is in
    the name of a refusal: without it the second would overwrite the first and
    the collection would report one denial where there were two.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for document in collected.documents:
        resource = document["resource"]
        if resource["type"] == "tenant":
            stem = f"unavailable-{'-'.join(document['facts'])}"
        else:
            stem = f"{resource['type']}-{resource['native_id']}"
        path = directory / (_safe(stem) + ".json")
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written.append(path)
    return sorted(written)


def _safe(name: str) -> str:
    """A filename from an identifier this engine does not get to reshape."""
    return "".join(c if c.isalnum() or c in "-._" else "-" for c in name)


# ---------------------------------------------------------------------------
# running it: one collection, with the same account of itself as every other
# ---------------------------------------------------------------------------

#: Where the bearer token is read from.
#:
#: THE ENVIRONMENT AND NEVER AN ARGUMENT. A token passed on the command line is
#: in the process list for every account on the machine and in the shell history
#: afterwards, and this engine never acquires one: it spends what somebody
#: already holds, which is the whole of its relationship with consent.
TOKEN_VARIABLE = "M365_GOVERNANCE_GRAPH_TOKEN"

#: How to produce one, for somebody who has a PnP session and no token.
HOW = (
    "Connect-PnPOnline -Url https://<tenant>.sharepoint.com -Interactive "
    "-ClientId <app>\n"
    "$env:" + TOKEN_VARIABLE + " = Get-PnPAccessToken -ResourceTypeName Graph"
)


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
    """Collect the slice and write its account of itself beside the evidence.

    The outcome is the same type a PowerShell collection produces, and it earns
    its state the same way: from what was written and what the documents say
    they could not read, never from a return code chosen here. A collection that
    was denied every area wrote three documents saying so, which is `partial` —
    evidence that a reader can act on — and not `completed`.
    """
    started_at = collecting._now()
    started = time.monotonic()

    try:
        reader = GraphReader(token, endpoint=endpoint, transport=transport)
    except Refused as refused:
        # No token, or nothing that can be read as one. Nothing was requested,
        # so there is no coverage to report and no document to write: the
        # collection did not happen.
        return collecting.Outcome(
            slice_name=NAME,
            returncode=2,
            seconds=time.monotonic() - started,
            written=[],
            stdout="",
            stderr=str(refused),
            started_at=started_at,
            finished_at=collecting._now(),
        )

    collected = collect(reader, tenant_url=tenant_url, observed_at=collecting._now())
    written = write(collected, output)

    if on_progress is not None:
        for area in collected.requested:
            reason = collected.unavailable.get(area)
            on_progress(
                f"{area}: read" if reason is None else f"{area}: {reason['state']}"
            )

    outcome = collecting.Outcome(
        slice_name=NAME,
        # Zero because the reader returned rather than failed. Whether the
        # collection is complete is a question the coverage answers, and an exit
        # code standing in for it is the collapse the states exist to end.
        returncode=0,
        seconds=time.monotonic() - started,
        written=written,
        stdout="",
        stderr="",
        incomplete=collecting.incomplete_coverage(written),
        started_at=started_at,
        finished_at=collecting._now(),
    )
    outcome.manifest_path = collecting.write_manifest(
        outcome,
        directory=output,
        client_id=client_id,
        site_url=None,
        tenant_url=tenant_url,
        device_login=False,
    )
    return outcome
