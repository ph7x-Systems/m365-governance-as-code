"""What is wrong with this installation, before anybody opens an issue.

Every check says what it found, not only whether it liked it. A check that
prints `ok` and nothing else moves the question to the next person; a check
that prints the version it found lets somebody compare it with the one in the
bug report.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .resources import BUNDLED, missing, packaged
from .validator import validate_rules

#: Below this, the code does not run. StrEnum and the typing syntax used here
#: both arrived in 3.11.
MINIMUM_PYTHON = (3, 11)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    #: A check that fails without stopping the tool from working. The
    #: collector is optional: the engine, the rules and the tests do not need
    #: PowerShell, and saying otherwise would send somebody installing things
    #: they do not use.
    required: bool = True

    def render(self) -> str:
        mark = "ok  " if self.ok else ("FAIL" if self.required else "none")
        # ljust plus a space, not a fixed field: a name longer than the field
        # ran straight into the detail and produced "schema.jsonvalid".
        return f"  {mark}  {self.name.ljust(24)} {self.detail}"


def _python() -> list[Check]:
    version = sys.version_info
    return [
        Check(
            "python",
            version[:2] >= MINIMUM_PYTHON,
            f"{platform.python_version()} "
            f"(needs {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or later)",
        ),
        Check("m365-governance", True, __version__),
        Check("platform", True, f"{platform.system()} {platform.machine()}"),
    ]


def _dependencies() -> list[Check]:
    checks = []
    for module, label in (("yaml", "PyYAML"), ("jsonschema", "jsonschema")):
        try:
            import importlib
            import importlib.metadata as meta

            importlib.import_module(module)
            checks.append(Check(label, True, meta.version(label)))
        except Exception as exc:  # noqa: BLE001 - reporting, not handling
            checks.append(Check(label, False, f"not usable: {exc}"))
    return checks


def _schemas(root: Path | None) -> list[Check]:
    from jsonschema import Draft202012Validator

    directory = _content(root, "schemas")
    if not directory.is_dir():
        return [Check("schemas", False, f"{directory} not found")]

    checks = []
    for path in sorted(directory.glob("*.json")):
        try:
            Draft202012Validator.check_schema(json.loads(path.read_text()))
            checks.append(Check(f"schema {path.name}", True, "valid"))
        except Exception as exc:  # noqa: BLE001
            checks.append(Check(f"schema {path.name}", False, str(exc)))
    return checks or [Check("schemas", False, "no schema files")]


def _rules(root: Path | None) -> list[Check]:
    directory = _content(root, "rules")
    if not directory.is_dir():
        return [Check("rules", False, f"{directory} not found")]
    problems = validate_rules(directory)
    count = len(list(directory.rglob("*.yaml")))
    if problems:
        first = str(problems[0])
        return [
            Check(
                "rules",
                False,
                f"{count} rules, {len(problems)} problems. First: {first}",
            )
        ]
    return [Check("rules", True, f"{count} rules, no problems")]


def _profiles(root: Path | None) -> list[Check]:
    import yaml

    directory = _content(root, "profiles")
    if not directory.is_dir():
        return [Check("profiles", False, f"{directory} not found")]

    rules_dir = _content(root, "rules")
    known = {p.stem for p in rules_dir.rglob("*.yaml")} if rules_dir.is_dir() else set()

    checks = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        # No `rules` key selects every rule. This read `len(selected)` on the
        # raw value and reported the default profile as selecting zero of
        # sixteen, next to the line saying nothing was broken. A diagnostic is
        # consulted precisely when somebody is already unsure.
        chooses = data.get("rules")
        selected = chooses if chooses else sorted(known)
        every = not chooses
        missing = [r for r in selected if r not in known]
        if missing:
            checks.append(
                Check(
                    f"profile {path.stem}",
                    False,
                    f"selects rules that do not exist: {missing}",
                )
            )
        else:
            detail = f"{len(selected)} rules selected"
            if every:
                detail += " (every rule: the profile names none)"
            checks.append(Check(f"profile {path.stem}", True, detail))
    return checks or [Check("profiles", False, "no profiles")]


#: How to install PowerShell 7, on the system asking.
#:
#: THE ONLY PLACE THIS ENGINE BRANCHES ON A PLATFORM, and it decides nothing:
#: it selects a sentence. Everything else here is platform-blind on purpose,
#: because a governance conclusion that differed by operating system would be a
#: conclusion about the operating system.
#:
#: IT WAS A URL, AND THAT IS HALF A DIAGNOSIS. The contract asks for the whole
#: of it — name what is missing AND how to obtain it — and the check below has
#: given the exact command for PnP.PowerShell all along, while the earlier one
#: sent the reader to a download page to work out which of six installers
#: applies. `run` compounded it by telling people that `doctor` gives the
#: command, which was not true until now.
#:
#: Linux keeps the link, and that is the honest answer rather than a gap: the
#: command differs by distribution, and printing one distribution's would be
#: wrong for most readers of it.
POWERSHELL_INSTALL = {
    "Darwin": "brew install --cask powershell",
    "Windows": "winget install --id Microsoft.PowerShell",
}

#: Where to go when no single command is right. Microsoft's own page, which
#: keeps the per-distribution instructions current so that this file does not.
POWERSHELL_DOCS = "https://aka.ms/powershell-release"


def _powershell_remedy() -> str:
    command = POWERSHELL_INSTALL.get(platform.system())
    if command:
        return f"install it with: {command}"
    return f"install it for your distribution: {POWERSHELL_DOCS}"


#: Which module each acquisition surface needs, and what a person types to get
#: it. A COLLECTOR'S PREREQUISITE BELONGS TO THE PRODUCT, NOT TO THE MACHINE IT
#: HAPPENS TO RUN ON. A licensing run on a host without the Graph modules
#: reported `not-supported` with the limitation owned by this implementation,
#: which was accurate and left the reader to work out what to install. The
#: alternative to naming them here is that a clean machine reproduces that
#: result every time and calls it a product limit.
COLLECTOR_MODULES = (
    (
        "PnP.PowerShell",
        "SharePoint collection",
        "Install-Module PnP.PowerShell -Scope CurrentUser",
    ),
    (
        "Microsoft.Graph.Identity.DirectoryManagement",
        "licensing: subscribed SKUs",
        "Install-Module Microsoft.Graph.Identity.DirectoryManagement"
        " -Scope CurrentUser",
    ),
    (
        "Microsoft.Graph.Users",
        "licensing: per-user assignments",
        "Install-Module Microsoft.Graph.Users -Scope CurrentUser",
    ),
    (
        "Microsoft.Graph.Reports",
        "licensing: usage reports",
        "Install-Module Microsoft.Graph.Reports -Scope CurrentUser",
    ),
)


def _module_version(pwsh: str, name: str) -> str:
    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            f"(Get-Module -ListAvailable {name} | Select-Object -First 1)"
            ".Version.ToString()",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    return result.stdout.strip()


def _powershell() -> list[Check]:
    """The collectors only. Absent is not a failure: the engine never needs it."""
    pwsh = shutil.which("pwsh")
    if not pwsh:
        return [
            Check(
                "PowerShell 7",
                False,
                f"not found. Only the collectors need it. {_powershell_remedy()}",
                required=False,
            ),
            *[
                Check(name, False, f"not checked ({what})", required=False)
                for name, what, _ in COLLECTOR_MODULES
            ],
        ]

    checks = [Check("PowerShell 7", True, pwsh)]
    for name, what, remedy in COLLECTOR_MODULES:
        try:
            version = _module_version(pwsh, name)
        except Exception as exc:  # noqa: BLE001
            checks.append(Check(name, False, f"could not check: {exc}", required=False))
            continue

        if version:
            checks.append(Check(name, True, f"{version} ({what})"))
        else:
            # NOT REQUIRED, AND NOT SILENT. The engine runs without any of
            # these; the acquisition surface each one serves does not, and it
            # says which surface rather than leaving a bare module name.
            checks.append(
                Check(
                    name,
                    False,
                    f"not installed. {what} needs it. {remedy}",
                    required=False,
                )
            )
    return checks


def _content(root: Path | None, name: str) -> Path:
    """Where to look for one kind of content.

    `None` means what shipped with this version, which is the default and the
    case that matters: `doctor` is what somebody runs when an install is not
    behaving, and it has to describe the installation rather than whatever
    directory they happen to be standing in.
    """
    if root is not None:
        return root / name
    return packaged(name)


def _packaging() -> list[Check]:
    """Whether the installed package contains the product.

    This check exists because it once would have failed. Before the content
    moved inside the package, `pip install` produced a command-line tool with
    no rules, profiles, schemas or collector, and `doctor` reported three
    directories missing from the working directory as though the user had
    stood in the wrong place.
    """
    absent = missing()
    if absent:
        return [
            Check(
                "packaged content",
                False,
                f"this installation is missing {', '.join(absent)}. The package "
                "was built without its own content; reinstall from a release.",
            )
        ]
    return [Check("packaged content", True, f"{', '.join(BUNDLED)}")]


def run(root: Path | None = None) -> tuple[list[tuple[str, list[Check]]], bool]:
    groups = [
        ("Environment", _python() + _dependencies()),
        ("Installation", _packaging()),
        ("Schemas", _schemas(root)),
        ("Rules and profiles", _rules(root) + _profiles(root)),
        ("Collector, optional", _powershell()),
    ]
    healthy = all(c.ok or not c.required for _, checks in groups for c in checks)
    return groups, healthy


def report(root: Path | None = None) -> tuple[str, bool]:
    groups, healthy = run(root)
    where = str(root) if root is not None else "the installed package"
    lines = [f"m365-governance doctor    reading content from: {where}", ""]
    for title, checks in groups:
        lines.append(title)
        lines.extend(check.render() for check in checks)
        lines.append("")

    failures = [c for _, checks in groups for c in checks if not c.ok and c.required]
    optional = [
        c for _, checks in groups for c in checks if not c.ok and not c.required
    ]

    if failures:
        lines.append(f"{len(failures)} problem(s) that stop the tool working.")
    else:
        lines.append("Nothing is broken.")
    if optional:
        lines.append(
            f"{len(optional)} optional component(s) absent. The engine, the "
            f"rules and the tests do not need them."
        )
    return "\n".join(lines) + "\n", healthy
