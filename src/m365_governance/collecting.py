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

import json
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from .resources import packaged

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
        ),
        Slice(
            "sites",
            "TenantSites",
            needs_site=False,
            needs_tenant=True,
            profile="capacity",
            describes="every site this identity can enumerate",
            shaped_like="site-storage-comfortable",
        ),
        Slice(
            "owners",
            "SiteOwners",
            needs_site=True,
            needs_tenant=False,
            profile="ownership",
            describes="who administers one site",
            shaped_like="site-named-and-group-admins",
        ),
        Slice(
            "modernity",
            "Modernity",
            needs_site=True,
            needs_tenant=False,
            profile="modernisation",
            describes="how one site is built: template, branding, publishing",
            shaped_like="site-modern-publishing-on",
        ),
        Slice(
            "sharing",
            "SiteSharing",
            needs_site=True,
            needs_tenant=True,
            profile="sharing",
            describes="what one site permits, and its default link",
            shaped_like="site-sharing-anyone-default-anyone",
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
        ),
        Slice(
            "activity",
            "Activity",
            needs_site=True,
            needs_tenant=True,
            profile="activity",
            describes="when a person last changed something on one site",
            shaped_like="site-activity-stale",
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
        ),
        Slice(
            "permissions",
            "UniquePermissions",
            needs_site=True,
            needs_tenant=False,
            profile="capacity",
            describes="every visible list on a site, and its inheritance",
            shaped_like="list-within-limit",
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

    #: Set only when the caller stopped it. Nothing infers cancellation from an
    #: exit code: a collector killed by the network and one stopped by a person
    #: exit the same way, and only the caller knows which happened.
    cancelled: bool = False

    #: What the written documents said they could not read, one entry per
    #: document that fell short. Read from the artefacts rather than guessed
    #: from the exit code.
    incomplete: list[str] = field(default_factory=list)

    @property
    def state(self) -> State:
        if self.cancelled:
            return State.CANCELLED
        if self.returncode != 0:
            # A collector that died having written documents produced evidence
            # worth exactly those documents. Calling that `failed` throws away
            # what it did read, which is the collapse this type exists to end.
            return State.PARTIAL if self.written else State.FAILED
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
        # is the one moment somebody might want to stop it.
        return Outcome(name, 0, 0.0, [], " ".join(argv), "")

    before = _files(output)
    started = time.monotonic()
    returncode, out, err, cancelled = _run(argv, on_progress)
    elapsed = time.monotonic() - started
    written = sorted(set(_files(output)) - set(before))

    return Outcome(
        slice_name=name,
        returncode=returncode,
        seconds=elapsed,
        written=written,
        stdout=out,
        stderr=err,
        cancelled=cancelled,
        incomplete=incomplete_coverage(written),
    )


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
    linhas: list[str] = []
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
            for linha in child.stdout:
                linha = linha.rstrip("\n")
                linhas.append(linha)
                if on_progress is not None:
                    on_progress(linha)
            returncode = child.wait()
        except KeyboardInterrupt:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
            cancelled = True
            returncode = child.returncode if child.returncode is not None else 130

    return returncode, "\n".join(linhas), "", cancelled


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
    fora = []
    for caminho in written:
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            fora.append(f"{caminho.name}: cannot be read as evidence ({exc})")
            continue
        cobertura = dados.get("coverage")
        if not isinstance(cobertura, dict):
            fora.append(f"{caminho.name}: no coverage recorded")
            continue
        pedido = set(cobertura.get("requested") or [])
        feito = set(cobertura.get("completed") or [])
        em_falta = sorted(pedido - feito)
        if em_falta:
            indisponivel = cobertura.get("unavailable") or {}
            razoes = "; ".join(
                f"{k}: {v}" for k, v in indisponivel.items() if k in em_falta
            )
            fora.append(
                f"{caminho.name}: {', '.join(em_falta)} not read"
                + (f" ({razoes})" if razoes else "")
            )
    return fora


def _files(output: Path) -> list[Path]:
    if output.is_dir():
        return sorted(output.rglob("*.json"))
    return [output] if output.exists() else []
