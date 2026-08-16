#!/usr/bin/env python3
"""The observable surface, measured rather than imagined.

The question a governance engine has to keep asking is not "what shall we
build" but **what can be observed that we are not observing**. That is
answerable: the collector's own source says what it reads, and the installed
PnP module says what can be read.

    docs/OBSERVABLE-SURFACE.md   the gap, grouped by governance area

`--check` regenerates into memory and fails when the file on disk is stale, so
the measurement cannot rot. Like every other derived artefact here, it has a
generator and a check rather than a person remembering to update it.

**This produces candidates, not decisions.** A cmdlet appearing here is a
surface somebody could read; whether it should become evidence, and whether a
rule could be written on it, is the rule contract's question and it starts with
a documented basis. A cmdlet is not a reason.

Needs PowerShell with PnP.PowerShell installed; skips cleanly without it.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTORS = ROOT / "src" / "m365_governance" / "data" / "collectors"
OUT = ROOT / "docs" / "OBSERVABLE-SURFACE.md"

#: How a cmdlet name maps onto something a governance product asks about. The
#: only declared thing in this file, because a name is not a category and
#: nothing in the module says which area a cmdlet serves.
AREAS = {
    "Sharing and external access": r"Sharing|Anonymous|External|Guest",
    "Permissions and identity": (
        r"Permission|Role|EntraID|ServicePrincipal|AppRole|Access"
    ),
    "Classification and labels": (
        r"Label|Sensitivity|Classification|Retention|Compliance"
    ),
    "Tenant configuration": r"Tenant(?!Site)",
    "Sites and structure": r"Site|Web|Hub|SubWeb|Template",
    "Content and lists": r"List|Item|Field|ContentType|Folder|File(?!Retention)",
    "Modernity and customisation": r"Page|Feature|CustomAction|Theme|Branding|Master",
    "Applications and extensions": r"App|Spfx|Solution|AddIn",
    "Automation": r"Flow|Workflow|PowerAutomate",
    "Collaboration": r"Teams|Group|Yammer|Viva|Planner",
    "Auditing and activity": r"Audit|Activity|Report|Log",
}


def read_cmdlets() -> list[str] | None:
    """Every read-only cmdlet the installed module exposes."""
    if not shutil.which("pwsh"):
        return None

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            "Import-Module PnP.PowerShell -ErrorAction Stop; "
            "(Get-Command -Module PnP.PowerShell | "
            "Where-Object { $_.Verb -in @('Get','Find','Measure','Test') }).Name",
        ],
        capture_output=True,
        text=True,
    )
    return sorted(set(result.stdout.split())) if result.returncode == 0 else None


#: The same reading the read-only gate does, asked for command names instead of
#: for mutating verbs. Kept out of the f-string so the line length is the
#: script's own rather than an artefact of indentation.
_AST_SCRIPT = """
$names = @()
$files = Get-ChildItem -Recurse '<ROOT>' -Include *.ps1, *.psm1
foreach ($file in $files) {
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $file.FullName, [ref]$null, [ref]$null)
    $commands = $ast.FindAll({
        param($n)
        $n -is [System.Management.Automation.Language.CommandAst]
    }, $true)
    $names += $commands | ForEach-Object { $_.GetCommandName() }
}
$names | Where-Object { $_ } | Sort-Object -Unique
"""


def used() -> set[str]:
    """What the collector actually calls, from its own syntax tree.

    PARSED, NOT GREPPED, and the difference is a claim this document makes
    about itself. A regular expression over the source counts every mention:
    the moment a comment explained why `Get-PnPTenantId` was NOT being called,
    the measurement said it was, and the published surface asserted a
    collection path that does not exist.

    The AST is already how the read-only gate proves there is no write path, so
    this is the same reading applied to the same files. A cmdlet named inside a
    comment or a help block is not a call, and a cmdlet reached through a
    variable is still invisible to both -- which is a floor under review rather
    than a substitute for it, and the same caveat the read-only gate carries.
    """
    if not shutil.which("pwsh"):
        return set()

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            _AST_SCRIPT.replace("<ROOT>", str(COLLECTORS)),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()

    called = set(result.stdout.split())
    return {name for name in called if re.fullmatch(r"(?:Get|Test)-PnP\w+", name, re.I)}


def version() -> str:
    if not shutil.which("pwsh"):
        return "unknown"
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            "(Get-Module -ListAvailable PnP.PowerShell | Sort-Object Version "
            "-Descending | Select-Object -First 1).Version.ToString()",
        ],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def render(available: list[str], reading: set[str]) -> str:
    unread = [c for c in available if c not in reading]

    lines = [
        "# The observable surface",
        "",
        "**Generated by `tools/surface.py`. Do not edit.**",
        "",
        "What can be read against what is read. The engine's coverage question "
        "asked of itself: not *what shall we build*, but **what can be observed "
        "that we are not observing**.",
        "",
        f"- PnP.PowerShell **{version()}**",
        f"- **{len(available)}** read-only cmdlets available",
        f"- **{len(reading & set(available))}** called by the collector",
        f"- **{len(unread)}** not called",
        "",
        "> **This is a list of candidates, not a backlog.** A cmdlet appearing "
        "here is a surface somebody *could* read. Whether it should become "
        "evidence, and whether a rule can be written on it, is the rule "
        "contract's question, and that starts with a documented basis. **A "
        "cmdlet is not a reason.**",
        "",
        "Two standing rules apply to everything below, and they are twins:",
        "",
        "> Never build a rule on a property until the collection path is proven "
        "to populate it.",
        ">",
        "> Never add a collection path that no rule can consume.",
        "",
        "## What the collector reads today",
        "",
    ]
    lines += [f"- `{c}`" for c in sorted(reading & set(available))]

    lines += ["", "## What it does not, by area", ""]
    claimed: set[str] = set()
    for area, pattern in AREAS.items():
        matched = [c for c in unread if re.search(pattern, c) and c not in claimed]
        if not matched:
            continue
        claimed.update(matched)
        lines += [f"### {area}", "", f"{len(matched)} cmdlets.", ""]
        lines += [f"- `{c}`" for c in sorted(matched)]
        lines.append("")

    rest = [c for c in unread if c not in claimed]
    if rest:
        lines += [
            "### Unclassified",
            "",
            "No area pattern matched these. An area missing from the map is "
            "more likely than a cmdlet that belongs nowhere.",
            "",
        ]
        lines += [f"- `{c}`" for c in sorted(rest)]
        lines.append("")

    lines += [
        "---",
        "",
        "**The number that matters is not how many are unread.** It is how many "
        "carry documented guidance somebody could write a rule against, and "
        "that is answered one area at a time, on Microsoft's pages, before any "
        "collection is added.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    available = read_cmdlets()
    if available is None:
        print("  PnP.PowerShell is not available; the surface was not measured")
        return 0

    wanted = render(available, used())

    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != wanted:
            print(f"  ✗ stale: {OUT.name} — run tools/surface.py")
            return 1
        print(f"  ✓ {len(available)} cmdlets measured, surface current")
        return 0

    OUT.write_text(wanted, encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
