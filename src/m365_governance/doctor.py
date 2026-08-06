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


def _schemas(root: Path) -> list[Check]:
    from jsonschema import Draft202012Validator

    directory = root / "schemas"
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


def _rules(root: Path) -> list[Check]:
    directory = root / "rules"
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


def _profiles(root: Path) -> list[Check]:
    import yaml

    directory = root / "profiles"
    if not directory.is_dir():
        return [Check("profiles", False, f"{directory} not found")]

    known = (
        {p.stem for p in (root / "rules").rglob("*.yaml")}
        if (root / "rules").is_dir()
        else set()
    )

    checks = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        selected = data.get("rules") or []
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
            checks.append(
                Check(f"profile {path.stem}", True, f"{len(selected)} rules selected")
            )
    return checks or [Check("profiles", False, "no profiles")]


def _powershell() -> list[Check]:
    """The collector only. Absent is not a failure: the engine never needs it."""
    pwsh = shutil.which("pwsh")
    if not pwsh:
        return [
            Check(
                "PowerShell 7",
                False,
                "not found. Only the collector needs it",
                required=False,
            ),
            Check("PnP.PowerShell", False, "not checked", required=False),
        ]

    checks = [Check("PowerShell 7", True, pwsh)]
    try:
        result = subprocess.run(
            [
                pwsh,
                "-NoProfile",
                "-Command",
                "(Get-Module -ListAvailable PnP.PowerShell | "
                "Select-Object -First 1).Version.ToString()",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
        version = result.stdout.strip()
        if version:
            checks.append(Check("PnP.PowerShell", True, version))
        else:
            checks.append(
                Check(
                    "PnP.PowerShell",
                    False,
                    "not installed. Install-Module PnP.PowerShell -Scope CurrentUser",
                    required=False,
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            Check("PnP.PowerShell", False, f"could not check: {exc}", required=False)
        )
    return checks


def run(root: Path) -> tuple[list[tuple[str, list[Check]]], bool]:
    groups = [
        ("Environment", _python() + _dependencies()),
        ("Schemas", _schemas(root)),
        ("Rules and profiles", _rules(root) + _profiles(root)),
        ("Collector, optional", _powershell()),
    ]
    healthy = all(c.ok or not c.required for _, checks in groups for c in checks)
    return groups, healthy


def report(root: Path) -> tuple[str, bool]:
    groups, healthy = run(root)
    lines = [f"m365-governance doctor    working directory: {root}", ""]
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
