"""The collector has no write path, and does not conclude.

A static check rather than a run: there is no tenant in CI, and there never
will be. What can be proved offline is that the script cannot change anything
and does not smuggle a judgement into the evidence.

Every check here walks **every** PowerShell file under the collectors
directory. It used to name one path, which was true when there was one file
and would have quietly stopped proving anything about the rest the moment the
collector was split into modules. See docs/POWERSHELL-STANDARDS.md.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from conftest import DATA

COLLECTORS = DATA / "collectors"
COLLECTOR = COLLECTORS / "powershell" / "sharepoint" / "Get-SpoEvidence.ps1"

#: Every `.ps1` and `.psm1` that ships. Sorted so a failure names the same file
#: on every machine.
POWERSHELL = sorted(p for p in COLLECTORS.rglob("*") if p.suffix in {".ps1", ".psm1"})

#: Verb-Noun forms that change something. Matched on the PnP and Graph command
#: surfaces, where a mutation is always one of these verbs.
MUTATING = re.compile(
    r"\b(Set|New|Remove|Add|Update|Grant|Revoke|Reset|Restore|Move|Rename|"
    r"Disable|Enable|Submit|Publish)-(PnP|Mg|SPO)\w+",
    re.IGNORECASE,
)

#: Fields that presume a rule. A collector that returns any of these has moved
#: the judgement out of a reviewable diff and into code.
CONCLUSIONS = (
    "is_compliant",
    "isCompliant",
    "risk",
    "score",
    "recommended_action",
    "recommendation",
    "severity",
)

FUNCTION = re.compile(r"^function\s+([A-Za-z]+)-(\w+)", re.MULTILINE)


def source() -> str:
    return COLLECTOR.read_text(encoding="utf-8")


def body(path) -> str:
    """The file without its leading comment block, which names the forbidden
    words precisely in order to forbid them."""
    text = path.read_text(encoding="utf-8")
    return text.split("#>", 1)[1] if "#>" in text else text


def test_the_collector_exists():
    assert COLLECTOR.is_file()


def test_every_powershell_file_is_checked():
    """A guard on the guards. If this list were ever empty — a moved
    directory, a renamed suffix — every check below would pass by walking
    nothing."""
    assert POWERSHELL
    assert COLLECTOR in POWERSHELL


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_no_powershell_file_has_a_write_path(path):
    found = MUTATING.findall(path.read_text(encoding="utf-8"))
    assert not found, f"mutating cmdlet in a read-only collector: {found}"


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_no_powershell_file_returns_a_conclusion(path):
    offenders = [word for word in CONCLUSIONS if word in body(path)]
    assert not offenders, f"a collector may not decide: {offenders}"


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_every_powershell_file_fails_loudly(path):
    """`Set-StrictMode` turns a misspelled property into an error instead of
    into a `$null` that reaches an evidence envelope looking like an observed
    absence. `Stop` keeps a failed read from being walked past."""
    text = path.read_text(encoding="utf-8")
    assert "Set-StrictMode -Version Latest" in text
    assert "$ErrorActionPreference = 'Stop'" in text


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_every_function_uses_an_approved_verb(path):
    """Microsoft's list, read from the installed PowerShell rather than
    copied here, so it cannot go stale against the runtime that will load
    these files.

    https://learn.microsoft.com/powershell/scripting/developer/cmdlet/approved-verbs-for-windows-powershell-commands
    """
    if not shutil.which("pwsh"):
        pytest.skip("pwsh is not installed; only collection needs it")

    approved = set(
        subprocess.run(
            ["pwsh", "-NoProfile", "-Command", "(Get-Verb).Verb"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    used = {verb for verb, _ in FUNCTION.findall(path.read_text(encoding="utf-8"))}
    assert used <= approved, f"unapproved verb: {sorted(used - approved)}"


def test_the_collector_records_identity_kind():
    """Without it, a delegated run reads as a tenant-wide statement."""
    assert any("identity_kind" in p.read_text(encoding="utf-8") for p in POWERSHELL)


def test_the_collector_never_returns_an_empty_list_on_failure():
    """Every failure path must produce a state and a reason, not `@()`."""
    joined = "".join(body(p) for p in POWERSHELL)
    assert "New-Unavailable" in joined
    assert re.search(r"catch\s*\{[^}]*Resolve-FailureState", joined, re.DOTALL)


def test_group_expansion_is_declared_incomplete_rather_than_guessed():
    joined = "".join(p.read_text(encoding="utf-8") for p in POWERSHELL)
    assert "not-attempted" in joined
    assert "minimum_count" in joined


def test_a_slice_with_no_site_connects_to_the_admin_centre():
    """The Python side knows which slices pass a `-SiteUrl`; the PowerShell
    side decides where to connect. Nothing joined the two, and they diverged:
    `TenantSharing` was added to the collector's switch and not to its list of
    admin modes, so the mode asked for a `-SiteUrl` that its own slice never
    passes. It would have failed on the first tenant run and on no test.
    """
    from m365_governance import collecting

    connection = (COLLECTOR.parent / "modules" / "Connection.psm1").read_text(
        encoding="utf-8"
    )
    declared = re.search(r"\$script:AdminModes\s*=\s*@\(([^)]*)\)", connection)
    assert declared, "Connection.psm1 no longer declares $script:AdminModes"
    admin = set(re.findall(r"'([^']+)'", declared.group(1)))

    siteless = {s.mode for s in collecting.SLICES.values() if not s.needs_site}
    assert siteless <= admin, (
        f"slice modes with no -SiteUrl that would connect to one: "
        f"{sorted(siteless - admin)}"
    )
