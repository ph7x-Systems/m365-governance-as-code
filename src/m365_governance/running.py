"""One command from a configured target to a report.

WHY THIS EXISTS. A tenant assessed end to end was ten `collect` commands and
then an `evaluate`, and the person running them had to know what a slice is
before they could obtain a first result. Choosing among ten slices is a
decision this product is able to make from the target it was given, and asking
somebody to make it before they have seen a single finding is asking them to
learn the architecture in order to use the tool.

WHAT IT DOES NOT DO. It does not decide anything a rule decides, it does not
merge evidence, and it does not make a slice apply to a target it does not
apply to. It plans, runs what it planned, and says what it did not run.

**A SLICE THAT WAS NOT ATTEMPTED IS REPORTED, NEVER DROPPED.** This is the
engine's own rule arriving one layer earlier: missing evidence is a fact about
collection, and a run that quietly skipped half its slices would produce a
report that looks complete to the only person who could tell that it is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .collecting import SLICES, Slice


class Planned(StrEnum):
    """Whether a slice will be attempted, and if not, why not."""

    ATTEMPT = "attempt"
    """The target carries what this slice needs."""

    NO_SITE = "no-site"
    """It reads one site and no site address was configured."""

    NO_TENANT = "no-tenant"
    """It reads the organisation and no admin address was configured."""

    NO_TOKEN = "no-token"
    """It reads Microsoft Graph and no token is present in the environment."""

    NO_POWERSHELL = "no-powershell"
    """It runs through PowerShell and this machine has none."""


#: Why each refusal, in words a person can act on. Written here rather than
#: at the point of printing, so that the plan and the report of the run cannot
#: describe the same decision differently.
BECAUSE: dict[Planned, str] = {
    Planned.NO_SITE: "reads one site, and no site address is configured",
    Planned.NO_TENANT: "reads the organisation, and no admin address is configured",
    Planned.NO_TOKEN: (
        "reads Microsoft Graph, and this engine never acquires a token: "
        "set one in the environment to include it"
    ),
    Planned.NO_POWERSHELL: (
        "runs through PowerShell 7, and this machine has none: `doctor` "
        "gives the command for this system"
    ),
}


@dataclass(frozen=True)
class Step:
    """One slice, and what is going to happen to it."""

    slice: Slice
    planned: Planned

    @property
    def name(self) -> str:
        return self.slice.name

    @property
    def because(self) -> str:
        return BECAUSE.get(self.planned, "")


def plan(
    *,
    site_url: str | None,
    tenant_url: str | None,
    has_graph_token: bool,
    has_powershell: bool = True,
) -> list[Step]:
    """Every slice this engine holds, and whether the target reaches it.

    EVERY SLICE, NOT THE ONES THAT APPLY. The list is the whole catalogue with
    a verdict against each, because the value of the unattempted ones is
    exactly that somebody reads them: a target with no admin address cannot see
    the organisation's own sharing settings, and that is a fact about the run
    which no report over the collected evidence could recover.

    Ordered by name so that two runs of one version plan identically.
    """
    steps = []
    for name in sorted(SLICES):
        chosen = SLICES[name]
        if chosen.source == "graph" and not has_graph_token:
            planned = Planned.NO_TOKEN
        elif chosen.source == "powershell" and not has_powershell:
            # A PLAN THAT PROMISES WHAT THE MACHINE CANNOT DO IS THE DEFECT THIS
            # WHOLE COMMAND EXISTS TO AVOID. Observed on a clean machine,
            # 2026-08-20: with no PowerShell installed, `run --dry-run` printed
            # "Plan: 2 of 11 collections" and exited 0 — and a dry run is
            # precisely what somebody uses to find out whether they are ready.
            # The Graph slice already said its token was missing; the ten that
            # need an interpreter said nothing about it, and the engine knew.
            planned = Planned.NO_POWERSHELL
        elif chosen.needs_site and not site_url:
            planned = Planned.NO_SITE
        elif chosen.needs_tenant and not tenant_url:
            planned = Planned.NO_TENANT
        else:
            planned = Planned.ATTEMPT
        steps.append(Step(slice=chosen, planned=planned))
    return steps


def attempted(steps: list[Step]) -> list[Step]:
    return [step for step in steps if step.planned is Planned.ATTEMPT]


def describe(steps: list[Step]) -> str:
    """The plan, for a person, before anything reaches a tenant."""
    doing = attempted(steps)
    lines = [f"Plan: {len(doing)} of {len(steps)} collections", ""]
    for step in steps:
        if step.planned is Planned.ATTEMPT:
            lines.append(f"  run      {step.name:16} {step.slice.describes}")
    skipped = [s for s in steps if s.planned is not Planned.ATTEMPT]
    if skipped:
        lines.append("")
        for step in skipped:
            lines.append(f"  not run  {step.name:16} {step.because}")
        lines += [
            "",
            "  A collection that was not attempted is not a resource that is not",
            "  there. Nothing below reads these, and no rule over the evidence",
            "  can recover what they would have said.",
        ]
    return "\n".join(lines) + "\n"
