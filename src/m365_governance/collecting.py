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
    profile: str
    describes: str


SLICES = {
    s.name: s
    for s in [
        Slice(
            "sites",
            "TenantSites",
            needs_site=False,
            profile="ownership",
            describes="every site this identity can enumerate",
        ),
        Slice(
            "owners",
            "SiteOwners",
            needs_site=True,
            profile="ownership",
            describes="who administers one site",
        ),
        Slice(
            "sharing",
            "SiteSharing",
            needs_site=True,
            profile="sharing",
            describes="what one site permits, and its default link",
        ),
        Slice(
            "permissions",
            "UniquePermissions",
            needs_site=True,
            profile="capacity",
            describes="every visible list on a site, and its inheritance",
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
    else:
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
