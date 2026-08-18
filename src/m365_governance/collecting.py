"""Running a collector, and nothing else.

`collect` reads a tenant and writes evidence. It never evaluates a rule, and
the separation is deliberate rather than tidy: a command that collected and
judged in one step would produce a conclusion nobody could reproduce without
the tenant in front of them.

The evidence is a file. Anybody can read it, keep it, send it to somebody who
has no access, and evaluate it a year later against a different rule set. That
is the whole reason the two halves are separate.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import canonical, registry
from .resources import packaged

#: The manifest a collection writes beside its evidence, and the pattern a
#: consumer globs for.
#:
#: ONE FILE PER COLLECTION AND NEVER OVERWRITTEN. The documented layout gives
#: each slice its own directory, so the plain name is the ordinary case. It is
#: not enforced, and two collections pointed at one directory used to be
#: possible; the second would have replaced the first's account of itself with
#: no diagnostic, destroying the only record that the earlier one was partial.
#: A second collection in the same directory therefore carries its own short
#: identity in the filename instead.
MANIFEST = "collection-manifest.json"
MANIFEST_GLOB = "collection-manifest*.json"

#: What the manifest's digest is taken over: everything except the identity it
#: produces and the digest block that holds it. Naming them in the document
#: means a consumer verifying one does not have to know which engine wrote it.
DIGESTED = (
    "$schema",
    "acquisition",
    "artefacts",
    "because",
    "coverage",
    "exit_code",
    "finished_at",
    "identity",
    "observed",
    "requested",
    "seconds",
    "slice",
    "started_at",
    "state",
    "versions",
)

# Asked of the import system, not derived from this file's position. The
# previous form was `Path(__file__).resolve().parents[2] / "collectors" / ...`,
# which is right from `src/m365_governance/` and points at
# `lib/python3.x/collectors` from site-packages: plausible, anchored to
# `__file__` rather than to the working directory, and absent.
COLLECTOR = packaged("collectors") / "powershell" / "sharepoint" / "Get-SpoEvidence.ps1"


@dataclass(frozen=True)
class Slice:
    """One question, and the collector mode that answers it."""

    name: str
    mode: str
    #: The site is the unit for most of these; TenantSites walks the tenant.
    needs_site: bool
    #: Sharing settings are a tenant property about a site, so that slice
    #: needs the admin centre as well as the site. Discovered by running it.
    needs_tenant: bool
    profile: str
    describes: str
    #: A fixture shaped like what this slice produces. The pairing between a
    #: slice and its profile is tested against it, because the first pairing
    #: written here was wrong and only a real run showed it: `sites` gathers
    #: inventory, not owners, and pointing it at the ownership profile
    #: produced 106 `unknown` results across 53 sites.
    shaped_like: str
    #: Whether any rule consumes what this slice collects.
    #:
    #: The standing twin rule is that a collection path no rule can consume
    #: must not exist, and it holds: a path nobody reads is a maintenance cost
    #: with no output. `agents` is the first deliberate exception and it is
    #: recorded rather than smuggled past a test.
    #:
    #: Its evidence has no rule because the surface has no documented basis for
    #: one. Microsoft publishes nothing about how many agents an organisation
    #: should have or where they should live, so a threshold would be invented
    #: and a pass would mean nothing. The inventory is still worth collecting:
    #: the consumer is the report and any viewer, and `consumed_by` names it
    #: so that "no rule" never reads as "nobody looked".
    produces_findings: bool = True
    consumed_by: str = "governance rules"
    #: Whether `--output` is a directory or a single file.
    #:
    #: FOUND BY RUNNING IT. A slice that reads many resources writes one
    #: document per resource into a directory; a slice that reads one writes a
    #: file. The CLI accepted either for every slice, and the mismatch surfaced
    #: four seconds in as `Clear-Content is only supported on files.` -- an
    #: internal error from another language, to somebody with no way to know
    #: they passed the wrong kind of path.
    writes_many: bool = False
    #: Which Microsoft surface this slice reads, in that surface's own words.
    #:
    #: Declared rather than inferred, because nothing else in this repository
    #: knows it: the PowerShell collector names cmdlets and the Graph reader
    #: names paths, and a consumer asking "what does this product touch" was
    #: reading a prose table that nothing kept true.
    reads: tuple[str, ...] = ()
    #: Least privilege for this slice, as Microsoft documents it.
    permissions: tuple[str, ...] = ()
    #: What a run against a real tenant has established. The vocabulary is the
    #: matrix's, and this is now where it lives: the document is a projection.
    live: str = "not live-validated"
    #: Which collector answers this slice: `powershell` or `graph`.
    #:
    #: ONE REGISTRY AND TWO COLLECTORS. The alternative was a second list for
    #: Graph slices, and it would have meant a second `collect` command, a
    #: second manifest path and a second place to forget. What differs between
    #: the two is where the process runs and what it needs to authenticate;
    #: everything the manifest, the coverage and the reporting do with a slice
    #: is the same, so the difference is a field rather than a fork.
    source: str = "powershell"


SLICES = {
    s.name: s
    for s in [
        Slice(
            "agents",
            "Agents",
            needs_site=True,
            needs_tenant=False,
            profile="default",
            produces_findings=False,
            # SHIPPED TEXT. It named a particular private product, which put
            # that product's name into evidence a customer receives from a
            # public engine.
            consumed_by="the agent inventory in a report, and any viewer",
            describes="the Copilot agents in one site, and the sources each declares",
            shaped_like="site-agents-with-sources",
            reads=("Get-PnPWeb", "Get-PnPCopilotAgent"),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "sites",
            "TenantSites",
            needs_site=False,
            needs_tenant=True,
            profile="capacity",
            writes_many=True,
            describes="every site this identity can enumerate",
            shaped_like="site-storage-comfortable",
            reads=("Get-PnPTenantSite",),
            permissions=("AllSites.FullControl",),
            live="fully live-validated",
        ),
        Slice(
            "owners",
            "SiteOwners",
            needs_site=True,
            needs_tenant=False,
            profile="ownership",
            describes="who administers one site",
            shaped_like="site-named-and-group-admins",
            reads=("Get-PnPWeb", "Get-PnPSiteCollectionAdmin"),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "modernity",
            "Modernity",
            needs_site=True,
            needs_tenant=False,
            profile="modernisation",
            describes="how one site is built: template, branding, publishing",
            shaped_like="site-modern-publishing-on",
            reads=("Get-PnPWeb", "Get-PnPList", "Get-PnPFeature", "Get-PnPPage"),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "sharing",
            "SiteSharing",
            needs_site=True,
            needs_tenant=True,
            profile="sharing",
            describes="what one site permits, and its default link",
            shaped_like="site-sharing-anyone-default-anyone",
            reads=("Get-PnPWeb", "Get-PnPSite", "Get-PnPTenantSite"),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "tenant-sharing",
            "TenantSharing",
            needs_site=False,
            needs_tenant=True,
            profile="tenant-sharing",
            describes=(
                "what the organisation permits, which every site inherits by default"
            ),
            shaped_like="tenant-sharing-default-anyone-and-edit",
            reads=("Get-PnPTenant",),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "activity",
            "Activity",
            needs_site=True,
            needs_tenant=True,
            profile="activity",
            describes="when a person last changed something on one site",
            shaped_like="site-activity-stale",
            reads=("Get-PnPWeb", "Get-PnPTenantSite"),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "classification",
            "Classification",
            needs_site=True,
            needs_tenant=False,
            # No profile of its own, and that is a decision rather than an
            # omission. A profile selects rules, and the three classification
            # rules are the only ones that read this evidence, so a profile
            # naming them would repeat what the evidence already says.
            profile="default",
            describes="what a site records about the kind of content it holds",
            shaped_like="site-class-group-unlabelled",
            reads=("Get-PnPWeb", "Get-PnPSite"),
            permissions=(),
            live="live-validated",
        ),
        Slice(
            "permissions",
            "UniquePermissions",
            needs_site=True,
            needs_tenant=False,
            profile="capacity",
            writes_many=True,
            describes="every visible list on a site, and its inheritance",
            shaped_like="list-within-limit",
            reads=("Get-PnPList", "Get-PnPListItem"),
            permissions=(),
            live="live-validated",
        ),
        # SpfxCatalog only. The catalog is one call and feeds SPO-SPFX-001;
        # SpfxPages is a second, expensive mode whose evidence no rule reads
        # yet, so it stays a script-only mode rather than a slice that would
        # answer nothing about its own collection.
        Slice(
            "spfx",
            "SpfxCatalog",
            needs_site=True,
            needs_tenant=False,
            profile="spfx",
            describes="a site's app catalog: which solutions lag their version",
            shaped_like="site-spfx-behind",
            reads=("Get-PnPApp",),
            permissions=(),
            live="negative path validated",
        ),
        Slice(
            "conditional-access",
            "ConditionalAccess",
            source="graph",
            needs_site=False,
            # The admin centre address, and not because Graph needs it. The
            # token says which DIRECTORY the session opened in; the host is the
            # organisation's address, and evidence collected here has to carry
            # the same tenant identity as evidence collected from SharePoint or
            # an assessment would hold two tenants that are one.
            needs_tenant=True,
            profile="default",
            writes_many=True,
            produces_findings=False,
            # The second recorded exception to the twin rule, on the same terms
            # as `agents`: an inventory whose consumer is named. Microsoft
            # publishes no normative conclusion about which Conditional Access
            # policies an organisation should have, so a threshold invented here
            # would make a pass mean nothing. What the tenant has is worth
            # collecting; what it ought to have is not this engine's to assert.
            consumed_by="the access-policy inventory in a report, and any viewer",
            describes=(
                "the Conditional Access policies, named locations and Security "
                "Defaults state of one tenant"
            ),
            shaped_like="entra-conditional-access-mfa-for-admins",
            reads=(
                "GET /v1.0/identity/conditionalAccess/policies",
                "GET /v1.0/identity/conditionalAccess/namedLocations",
                "GET /v1.0/policies/identitySecurityDefaultsEnforcementPolicy",
            ),
            permissions=("Policy.Read.All",),
            live="provider live-validated, slice not live-validated",
        ),
    ]
}


class State(StrEnum):
    """How a collection ended, in four words rather than a boolean.

    `ok` was the whole answer, and it is an exit code wearing a name. A run
    that reached two hundred of three hundred sites and then lost its
    connection had the same value as one that never authenticated: the first
    produced evidence worth two hundred sites, and the second produced nothing.

    That collapse is made nowhere else in this engine. Coverage keeps
    `requested` and `completed` apart and names why a fact was unavailable; a
    rule answers `unknown` rather than failing when the gap could change its
    answer. The collection outcome was the one place a partial result and a
    failure were indistinguishable.
    """

    COMPLETED = "completed"
    """Everything the slice asked for."""

    PARTIAL = "partial"
    """Usable evidence, and less of the estate than was asked for."""

    FAILED = "failed"
    """No usable artefact."""

    CANCELLED = "cancelled"
    """Stopped deliberately. What was already written is kept, and says so."""


@dataclass
class Outcome:
    slice_name: str
    returncode: int
    seconds: float
    written: list[Path]
    stdout: str
    stderr: str

    #: Wall clock, and separate from `seconds`, which is monotonic. A reader
    #: compares these against a tenant's own change history; a duration
    #: subtracted from them would be wrong, occasionally negative, whenever the
    #: clock was adjusted mid-collection.
    started_at: str = ""
    finished_at: str = ""

    #: Where the account of this collection was written, and None when there
    #: was no directory to write it into — a dry run, or a caller that asked
    #: for a single file.
    manifest_path: Path | None = None

    #: Set only when the caller stopped it. Nothing infers cancellation from an
    #: exit code: a collector killed by the network and one stopped by a person
    #: exit the same way, and only the caller knows which happened.
    cancelled: bool = False

    #: What the written documents said they could not read, one entry per
    #: document that fell short. Read from the artefacts rather than guessed
    #: from the exit code.
    incomplete: list[str] = field(default_factory=list)

    #: False for a dry run, which describes a command and reaches no tenant.
    #:
    #: A COLLECTION THAT NEVER RAN HAS NO STATE. The four states are all
    #: statements about what a collector managed to do, and a dry run gave one
    #: nothing to do: reading it as `failed` would report a tenant as unread by
    #: a collection nobody asked to run, and as `completed` would be worse.
    attempted: bool = True

    @property
    def state(self) -> State:
        if not self.attempted:
            raise ValueError(
                "this is a dry run: it describes the command and reaches no "
                "tenant, so there is no collection to be in a state. The "
                "command is in `stdout`."
            )
        if self.cancelled:
            return State.CANCELLED
        if not self.written:
            # NO ARTEFACT IS `failed`, WHATEVER THE EXIT CODE. A clean exit that
            # produced nothing used to read as `completed`, which told a
            # consumer everything had been read by a collection that wrote
            # nothing down — the rounding-up these states exist to stop, made by
            # the type meant to stop it.
            #
            # A tenant with nothing in it lands here too, and that is the right
            # side of the line: the collection has no evidence to offer, and a
            # consumer that has to establish whether an estate is empty or was
            # never read should be told that nobody wrote anything, not that
            # everything went well.
            return State.FAILED
        if self.returncode != 0:
            # A collector that died having written documents produced evidence
            # worth exactly those documents. Calling that `failed` throws away
            # what it did read, which is the collapse this type exists to end.
            return State.PARTIAL
        return State.PARTIAL if self.incomplete else State.COMPLETED

    @property
    def ok(self) -> bool:
        """Kept, and deliberately narrow: it means the process exited zero.

        Callers deciding what a collection produced want `state`. This answers
        a different and smaller question, and the two are not synonyms: a
        partial collection can exit zero and a cancelled one cannot.
        """
        return self.returncode == 0


def preflight() -> list[str]:
    """What is missing before anything reaches a tenant."""
    problems = []
    if not shutil.which("pwsh"):
        problems.append(
            "PowerShell 7 is not installed. Only collection needs it; the "
            "engine, the rules and the tests do not."
        )
    if not COLLECTOR.is_file():
        problems.append(f"collector not found at {COLLECTOR}")
    return problems


def run_slice(
    name: str,
    *,
    client_id: str,
    output: Path,
    site_url: str | None = None,
    tenant_url: str | None = None,
    device_login: bool = False,
    count_unique_scopes: bool = False,
    dry_run: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> Outcome:
    """Run one slice against a tenant.

    `on_progress` receives each line the collector prints, as it prints it. It
    is optional and the default is silence, which is what a caller redirecting
    output wants.

    The output used to be buffered until the process exited. The collector
    writes progress, including how many sites an identity enumerated, and none
    of it reached the person waiting: `collect sites` against a large tenant
    printed nothing for however long it took and then printed everything. There
    was no stream to show, so nothing downstream could show one.
    """
    chosen = SLICES[name]
    if chosen.source != "powershell":
        # This function runs the PowerShell collector, and a slice answered by
        # another one would have produced a `-Mode` that collector has never
        # heard of. Refused here rather than four seconds into a process,
        # because a slice reaching the wrong collector is a routing defect and
        # not a tenant problem.
        raise ValueError(
            f"slice {name} is collected from {chosen.source}, not from the "
            f"PowerShell collector."
        )

    argv = [
        "pwsh",
        "-NoProfile",
        "-File",
        str(COLLECTOR),
        "-Mode",
        chosen.mode,
        "-ClientId",
        client_id,
        "-OutputPath",
        str(output),
    ]
    if chosen.needs_site:
        argv += ["-SiteUrl", site_url or ""]
    if chosen.needs_tenant:
        argv += ["-TenantUrl", tenant_url or ""]
    if device_login:
        argv.append("-DeviceLogin")
    if count_unique_scopes and chosen.mode == "UniquePermissions":
        argv.append("-CountUniqueScopes")

    if dry_run:
        # Printed before anything runs, because a collector reaching a tenant
        # is the one moment somebody might want to stop it. `attempted=False`,
        # so nothing downstream reads a state out of a collection that did not
        # happen, and no manifest is written: there is nothing to account for.
        return Outcome(name, 0, 0.0, [], " ".join(argv), "", attempted=False)

    before = _files(output)
    started_at = _now()
    started = time.monotonic()
    returncode, out, err, cancelled = _run(argv, on_progress)
    elapsed = time.monotonic() - started
    finished_at = _now()
    written = sorted(set(_files(output)) - set(before))

    outcome = Outcome(
        slice_name=name,
        returncode=returncode,
        seconds=elapsed,
        written=written,
        stdout=out,
        stderr=err,
        cancelled=cancelled,
        incomplete=incomplete_coverage(written),
        started_at=started_at,
        finished_at=finished_at,
    )

    # Written whatever happened, including a collection that produced nothing:
    # a failure that leaves no trace is a failure a consumer has to reconstruct
    # from an empty directory, which is the inference this contract exists to
    # remove.
    outcome.manifest_path = write_manifest(
        outcome,
        directory=_collection_directory(output),
        client_id=client_id,
        site_url=site_url,
        tenant_url=tenant_url,
        device_login=device_login,
    )
    return outcome


def _run(
    argv: list[str], on_progress: Callable[[str], None] | None
) -> tuple[int, str, str, bool]:
    """Run it, and hand each line over as it arrives.

    stderr is merged into stdout on purpose. Reading two pipes without select
    or threads deadlocks the moment either fills its buffer, and a collector
    that hangs at four hundred sites because nobody drained stderr would be a
    worse defect than the silence this replaces. The collector's own failure
    messages are therefore in the stream too, which is where somebody watching
    wants them.

    KeyboardInterrupt is a cancellation and not a crash: the child is asked to
    stop, whatever it already wrote to disk stays there, and the outcome says
    it was cancelled rather than that it failed.
    """
    lines: list[str] = []
    cancelled = False
    with subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as child:
        try:
            assert child.stdout is not None
            for line in child.stdout:
                line = line.rstrip("\n")
                lines.append(line)
                if on_progress is not None:
                    on_progress(line)
            returncode = child.wait()
        except KeyboardInterrupt:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
            cancelled = True
            returncode = child.returncode if child.returncode is not None else 130

    return returncode, "\n".join(lines), "", cancelled


def incomplete_coverage(written: list[Path]) -> list[str]:
    """Which of these documents read less than they set out to.

    Read from the artefacts, never inferred from the exit code. Every evidence
    document records `requested` against `completed`, and the difference is the
    engine's own account of what it did not see. A caller that guessed at
    partial from the number of files on disk would be inventing governance
    meaning from a side effect.

    A document this cannot parse is reported rather than skipped: a file that
    is not readable evidence is a reason to doubt the collection, and staying
    quiet about it would be the same rounding-up the outcome states exist to
    stop.
    """
    short = []
    for path in written:
        document = _evidence(path)
        if document is None:
            short.append(f"{path.name}: cannot be read as evidence")
            continue
        coverage = document.get("coverage")
        if not isinstance(coverage, dict):
            short.append(f"{path.name}: no coverage recorded")
            continue
        missing = sorted(
            set(coverage.get("requested") or []) - set(coverage.get("completed") or [])
        )
        if missing:
            unavailable = coverage.get("unavailable") or {}
            # The two fields, read out. It used to interpolate the whole entry,
            # so a sentence a person was meant to read arrived as a Python dict
            # repr, quotes and braces included, in the manifest and on stdout.
            reasons = "; ".join(
                f"{area}: {_reason(entry)}"
                for area, entry in unavailable.items()
                if area in missing
            )
            short.append(
                f"{path.name}: {', '.join(missing)} not read"
                + (f" ({reasons})" if reasons else "")
            )
    return short


def _reason(entry: Any) -> str:
    """Why an area was not read, as a sentence rather than as a structure."""
    if not isinstance(entry, dict):
        return str(entry)
    state, detail = entry.get("state"), entry.get("detail")
    return f"{state} — {detail}" if state and detail else str(detail or state or entry)


# ---------------------------------------------------------------------------
# the manifest: what the collection did, beside the evidence it produced
# ---------------------------------------------------------------------------


def build_manifest(
    outcome: Outcome,
    *,
    directory: Path,
    client_id: str,
    site_url: str | None,
    tenant_url: str | None,
    device_login: bool,
) -> dict[str, Any]:
    """The account of one collection, as a document.

    EVERYTHING HERE IS EITHER A FACT ABOUT THE INVOCATION OR READ BACK FROM THE
    ARTEFACTS. Nothing is inferred from the exit code, which is published raw
    and consumed as a verdict by nobody: the tenant, the identity kind, the
    collector version and the coverage all come from documents that were
    actually written, and are null or empty where none were.
    """
    chosen = SLICES[outcome.slice_name]
    documents = [(path, _evidence(path)) for path in outcome.written]

    body: dict[str, Any] = {
        "$schema": registry.contract("collection"),
        "state": str(outcome.state),
        "because": _because(outcome, documents),
        "slice": {
            "name": chosen.name,
            "mode": chosen.mode,
            "describes": chosen.describes,
            "profile": chosen.profile,
        },
        "started_at": outcome.started_at,
        "finished_at": outcome.finished_at,
        "seconds": round(outcome.seconds, 3),
        "exit_code": outcome.returncode,
        "requested": {"site_url": site_url, "tenant_url": tenant_url},
        "observed": _observed_tenant(documents),
        "identity": {
            "kind": _identity_kind(documents),
            "client_id": client_id,
            "device_login": device_login,
        },
        "acquisition": "collected",
        "versions": {
            "engine": _engine_version(),
            "contract": _contract_version(),
            "collector": _collector_version(documents),
        },
        "coverage": _union_coverage(documents),
        "artefacts": [_artefact(path, parsed, directory) for path, parsed in documents],
    }

    value = canonical.digest({k: body[k] for k in DIGESTED})
    body["collection_id"] = value
    body["digest"] = {
        "algorithm": canonical.ALGORITHM,
        "value": value,
        "covers": list(DIGESTED),
    }
    return body


def write_manifest(
    outcome: Outcome,
    *,
    directory: Path,
    client_id: str,
    site_url: str | None,
    tenant_url: str | None,
    device_login: bool,
) -> Path | None:
    """Write the manifest beside the evidence, without replacing another one.

    The directory is created where it does not exist, because a collection that
    failed before writing anything is exactly the case a consumer most needs an
    account of, and refusing to record it would leave an empty directory to be
    interpreted.
    """
    manifest = build_manifest(
        outcome,
        directory=directory,
        client_id=client_id,
        site_url=site_url,
        tenant_url=tenant_url,
        device_login=device_login,
    )

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST
    if path.exists() and _collection_id(path) != manifest["collection_id"]:
        # A second collection in a directory that already holds one. The first
        # one's account stays exactly where it is: overwriting it would destroy
        # the only record that it was partial.
        path = directory / f"collection-manifest.{manifest['collection_id'][:12]}.json"

    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def manifests(evidence: Path) -> list[dict[str, Any]]:
    """Every collection manifest under a path, as documents.

    THE ABSENCE OF ONE IS NOT A CLAIM ABOUT COMPLETENESS. Evidence collected
    before this contract existed, or exported from somewhere else, carries no
    manifest, and a caller reading an empty list here learns that nobody said —
    never that everything was read.
    """
    if evidence.is_file():
        found = [evidence] if evidence.name.startswith("collection-manifest") else []
    elif evidence.is_dir():
        found = sorted(evidence.rglob(MANIFEST_GLOB))
    else:
        return []

    documents = []
    for path in found:
        try:
            documents.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            # A manifest that cannot be read is reported by the schema layer
            # when something validates it. Here it is simply not an account.
            continue
    return documents


def _collection_id(path: Path) -> str | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("collection_id")
    except (OSError, json.JSONDecodeError):
        return None


def _because(outcome: Outcome, documents: list[tuple[Path, dict | None]]) -> list[str]:
    """Why the state is what it is, in the order the facts were established."""
    reasons = []
    if outcome.cancelled:
        reasons.append("the caller stopped the collector")
    if outcome.returncode != 0 and not outcome.cancelled:
        reasons.append(f"the collector exited {outcome.returncode}")
    reasons.append(f"{len(outcome.written)} evidence documents were written")
    unreadable = [path.name for path, parsed in documents if parsed is None]
    for name in unreadable:
        reasons.append(f"{name} could not be read back as evidence")
    reasons.extend(outcome.incomplete)
    if outcome.state is State.COMPLETED:
        reasons.append("every area each document requested was read")
    return reasons


def _artefact(path: Path, parsed: dict | None, directory: Path) -> dict[str, Any]:
    raw = path.read_bytes() if path.is_file() else b""
    try:
        relative = path.relative_to(directory)
    except ValueError:
        # Written outside the directory the manifest sits in. Rare, and the
        # absolute path is the truthful answer rather than a `..` chain that
        # stops resolving the moment either end moves.
        relative = path
    return {
        "path": str(relative).replace("\\", "/"),
        "digest": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "readable": parsed is not None,
    }


def _union_coverage(documents: list[tuple[Path, dict | None]]) -> dict[str, Any]:
    """The artefacts' coverage, unioned by area name and never counted.

    An area is `completed` only where every document that asked for it read it.
    One document reading an area another could not is not the collection having
    got all of it.
    """
    requested: set[str] = set()
    completed: set[str] = set()
    missing: set[str] = set()
    unavailable: dict[str, Any] = {}

    for _path, parsed in documents:
        coverage = (parsed or {}).get("coverage")
        if not isinstance(coverage, dict):
            continue
        asked = set(coverage.get("requested") or [])
        done = set(coverage.get("completed") or [])
        requested |= asked
        completed |= done
        missing |= asked - done
        for area, reason in (coverage.get("unavailable") or {}).items():
            if isinstance(reason, dict) and area not in unavailable:
                unavailable[area] = {
                    "state": reason.get("state"),
                    "detail": reason.get("detail"),
                }

    return {
        "requested": sorted(requested),
        "completed": sorted(completed - missing),
        "unavailable": unavailable,
    }


def _observed_tenant(documents: list[tuple[Path, dict | None]]) -> dict | None:
    for _path, parsed in documents:
        tenant = ((parsed or {}).get("provenance") or {}).get("tenant")
        if isinstance(tenant, dict):
            return tenant
    return None


def _identity_kind(documents: list[tuple[Path, dict | None]]) -> str:
    kinds = {
        ((parsed or {}).get("provenance") or {}).get("identity_kind")
        for _path, parsed in documents
    }
    kinds.discard(None)
    # One kind or none. Two would mean one collection ran under two identities,
    # which this engine has no way to produce and would not summarise if it did.
    return kinds.pop() if len(kinds) == 1 else "not-established"


def _collector_version(documents: list[tuple[Path, dict | None]]) -> str | None:
    for _path, parsed in documents:
        version = ((parsed or {}).get("provenance") or {}).get("collector_version")
        if isinstance(version, str):
            return version
    return None


def _engine_version() -> str:
    from . import __version__

    return __version__


def _contract_version() -> str:
    manifest = packaged("generated") / "manifest.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))["contract_version"]
    except (OSError, KeyError, json.JSONDecodeError):
        # The bundle is generated and committed; an installation without it is
        # still a working engine, and saying so beats inventing a version.
        return "not-published"


def _evidence(path: Path) -> dict | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _collection_directory(output: Path) -> Path:
    """Where the account of this collection goes.

    `--output` is a directory for the slices that write many documents and a
    file for the ones that write one, and the difference is not declared
    anywhere: it is probed. A path that does not exist yet is the failure case,
    and a `.json` suffix is the only signal available for it.
    """
    if output.is_dir():
        return output
    if output.suffix.lower() == ".json":
        return output.parent
    return output


def _files(output: Path) -> list[Path]:
    """The evidence under a path. Manifests are not evidence and never count.

    Without this exclusion a second collection into one directory would read
    the first one's manifest as a document it had just written, digest it as
    evidence, and report it as having no coverage.
    """
    if output.is_dir():
        return sorted(
            path
            for path in output.rglob("*.json")
            if not path.name.startswith("collection-manifest")
        )
    return [output] if output.exists() else []
