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

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

COLLECTOR = (
    Path(__file__).resolve().parents[2]
    / "collectors"
    / "powershell"
    / "sharepoint"
    / "Get-SpoEvidence.ps1"
)


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


SLICES = {
    s.name: s
    for s in [
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
    ]
}


@dataclass
class Outcome:
    slice_name: str
    returncode: int
    seconds: float
    written: list[Path]
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
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
) -> Outcome:
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
    result = subprocess.run(argv, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    written = sorted(set(_files(output)) - set(before))

    return Outcome(
        slice_name=name,
        returncode=result.returncode,
        seconds=elapsed,
        written=written,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _files(output: Path) -> list[Path]:
    if output.is_dir():
        return sorted(output.rglob("*.json"))
    return [output] if output.exists() else []
