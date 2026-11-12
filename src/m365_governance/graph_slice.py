"""What every Graph slice does the same way, written once.

WHY THIS FILE EXISTS. The first Graph slice carried its own document builder,
its own refusal builder, its own filename rule and its own runner. None of that
was about Conditional Access; all of it was about being a Graph slice. The cost
did not show until somebody asked for a second one, and then it showed as the
only thing that matters here: **the catalogue was twenty-one SharePoint rules
and five others, and the reason was that a new area of Microsoft 365 cost two
hundred lines of machinery before it could carry its first rule.**

So the machinery is here and the slices carry what is theirs: which paths they
read, which fields they are prepared to answer about, and what a resource of
theirs is called. A slice module that grows a second copy of anything in this
file is a slice that will be wrong in a way its neighbour is not.

WHAT IS DELIBERATELY NOT HERE: the areas, the addressable fields, the resource
types and the vocabulary a reader sees. Those are the product's decisions, one
per slice, and a shared table of them would make every slice depend on every
other slice's editorial choices.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import collecting, registry
from .graph import GraphReader, Read, Refused, Transport

#: Where the bearer token is read from, for every Graph slice.
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

#: How an unreadable area is named in `coverage.unavailable`, whose vocabulary
#: is four words and does not include `invalid`.
#:
#: RECORDED, NOT SMUGGLED. A `200` carrying something that is not readable as
#: Graph is `invalid` to the reader and has no word of its own in the evidence
#: contract, so it lands on `missing` -- nobody read it -- with the reader's own
#: sentence kept intact.
COVERAGE_STATE = {"invalid": "missing"}


@dataclass(frozen=True)
class Origin:
    """Who collected this, as the provenance of every document will say it."""

    collector: str
    collector_version: str
    workload: str
    source_system: str


def key(area: str) -> str:
    """The area name as a facts key, which rules read by name."""
    return area.replace("-", "_")


def coverage_state(state: str) -> str:
    return COVERAGE_STATE.get(state, state)


def addressable(
    fields: dict[str, str], item: dict[str, Any], *, of: str
) -> dict[str, Any]:
    """The fields of one object, as facts a rule can name.

    A PROPERTY THAT IS NOT THERE IS ABSENT, NOT FALSE. `isTrusted` is absent on
    a country location and present on an IP one, and a collector that wrote
    `false` for the first would have answered a question Microsoft did not.
    """
    out: dict[str, Any] = {}
    for name, prop in fields.items():
        if prop in item:
            out[name] = {
                "state": "observed",
                "value": item[prop],
                "raw": {"field": prop, "value": item[prop]},
            }
        else:
            out[name] = {
                "state": "missing",
                "detail": (
                    f"`{prop}` was not present on the object Microsoft returned. "
                    f"Absent is not false: the property is not published for "
                    f"every kind of {of}."
                ),
            }
    return out


def counted(
    name: str, item: dict[str, Any], prop: str, *, absent: str
) -> dict[str, Any]:
    """How many entries a returned collection holds, as a fact of its own.

    THE PATH GRAMMAR HAS NO WAY TO SAY `THIS ARRAY IS EMPTY`. `not-exists`
    tests whether a fact is present, and an object that publishes a present and
    empty array defeats a rule written against absence on exactly the case it
    exists to catch. A count is a fact about the object rather than a judgement
    about it, and it names the property it counted.
    """
    value = item.get(prop)
    if not isinstance(value, list):
        return {name: {"state": "missing", "detail": absent}}
    return {
        name: {
            "state": "observed",
            "value": len(value),
            "raw": {"field": prop, "value": value},
        }
    }


def document(
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
    origin: Origin,
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
        parent = {"workload": origin.workload, "type": "tenant", "native_id": host}

    return {
        "$schema": registry.contract("evidence"),
        "provenance": {
            "collected_at": observed_at,
            "collector": origin.collector,
            "collector_version": origin.collector_version,
            "source_system": origin.source_system,
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
            "workload": origin.workload,
            "type": resource_type,
            "native_id": native_id,
            "tenant": dict(tenant),
            "scope": scope,
            "parent": parent,
            "display_name": display_name,
        },
        "facts": facts,
    }


def refusal(
    area: str,
    read: Read,
    reader: GraphReader,
    host: str,
    observed_at: str,
    coverage: dict[str, Any],
    origin: Origin,
) -> dict[str, Any]:
    """An area that could not be read, as a fact about the tenant.

    THIS DOCUMENT IS THE POINT OF EVERY SLICE. Without it a denied read leaves
    the same directory as a tenant that genuinely has nothing configured, and a
    rule over that evidence would pass. With it the rule sees a fact whose state
    is not `observed` and answers `unknown`, which is the honest answer and the
    one nobody can act on by mistake.
    """
    assert read.unavailable is not None
    return document(
        reader,
        host,
        observed_at,
        coverage,
        origin,
        resource_type="tenant",
        native_id=host,
        display_name=host,
        facts={
            key(area): {
                "state": coverage_state(read.unavailable.state),
                "detail": read.unavailable.detail,
            }
        },
        scope="tenant",
        parent=None,
    )


def write(documents: list[dict[str, Any]], directory: Path) -> list[Path]:
    """Write one document per resource, into the directory the caller chose.

    The filename carries the resource type and its native id. Two areas that
    each refuse produce two documents about the same tenant, so the area is in
    the name of a refusal: without it the second would overwrite the first and
    the collection would report one denial where there were two.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for doc in documents:
        resource = doc["resource"]
        refused = all(
            isinstance(family, dict) and "state" in family
            for family in doc["facts"].values()
        )
        if resource["type"] == "tenant" and refused:
            stem = f"unavailable-{'-'.join(doc['facts'])}"
        elif resource["type"] == "tenant":
            # A tenant document that carries facts is an observation about the
            # tenant, and a name saying `unavailable` would describe the
            # opposite of what is in it.
            stem = f"tenant-{'-'.join(doc['facts'])}"
        else:
            stem = f"{resource['type']}-{resource['native_id']}"
        path = directory / (safe(stem) + ".json")
        path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written.append(path)
    return sorted(written)


def safe(name: str) -> str:
    """A filename from an identifier this engine does not get to reshape."""
    return "".join(c if c.isalnum() or c in "-._" else "-" for c in name)


def run(
    *,
    name: str,
    collect: Callable[[GraphReader, str, str], Any],
    token: str,
    output: Path,
    tenant_url: str,
    client_id: str = "",
    endpoint: str,
    transport: Transport | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> collecting.Outcome:
    """Collect one slice and write its account of itself beside the evidence.

    The outcome is the same type a PowerShell collection produces, and it earns
    its state the same way: from what was written and what the documents say
    they could not read, never from a return code chosen here. A collection that
    was denied every area wrote a document saying so for each, which is
    `partial` -- evidence that a reader can act on -- and not `completed`.
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
            slice_name=name,
            returncode=2,
            seconds=time.monotonic() - started,
            written=[],
            stdout="",
            stderr=str(refused),
            started_at=started_at,
            finished_at=collecting._now(),
        )

    collected = collect(reader, tenant_url, collecting._now())
    written = write(collected.documents, output)

    if on_progress is not None:
        for area in collected.requested:
            reason = collected.unavailable.get(area)
            on_progress(
                f"{area}: read" if reason is None else f"{area}: {reason['state']}"
            )

    outcome = collecting.Outcome(
        slice_name=name,
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

    # THE GRAPH SLICES LEAVE THEIR PROOF TOO, and until now they did not.
    #
    # The draft is what raises a collector out of `none`, and only the
    # PowerShell path wrote one -- so `tenant-governance` and
    # `conditional-access` could be run against a real directory, return real
    # evidence, decide thirteen rules, and still be published as never live
    # tested. The registry was not wrong: nothing had ever told it.
    #
    # The comment on the PowerShell side says a step somebody has to remember
    # is a step that gets skipped. That is exactly what happened here, one
    # layer up: the writer was remembered for one of the two collectors.
    collecting.write_proof_draft(outcome, name=name, output=output)
    return outcome
