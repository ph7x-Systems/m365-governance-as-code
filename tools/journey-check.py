#!/usr/bin/env python3
"""Walk the published journey on this machine, and say what a reader meets.

    python tools/journey-check.py

WHAT IT IS FOR. The release contract proves this repository. It does not prove
the artefact somebody installs, on the system they have. Every defect found on
2026-08-20 was found by running rather than by reading, with a green gate over
all of them, and the journey had met one operating system: the one it was built
on, which is not the one a Microsoft 365 administrator uses.

WHAT IT ASSERTS, AND WHY SO LITTLE. Exit codes and a few sentences. The
behaviour is tested elsewhere, in a suite that can be precise because it
controls its inputs. What this cannot get anywhere else is the same commands
against a real installation on a real operating system, so it checks the things
that break there: a console script that is not on PATH, a path separator, an
environment variable with another name, an interpreter that resolves to the
wrong version of itself.

IT NEVER REACHES A TENANT. Everything here runs with `--dry-run` or refuses
before the network, so it can run on every push without an identity and without
anybody's consent.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile

CONSOLE = "m365g"


def _tree_version() -> str:
    """The version this checkout would install, read from its packaging.

    The packaging metadata is the authority: it is what `pip` enforces, and a
    walk comparing against anything else would be comparing two guesses."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    found = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return found.group(1) if found else ""


GUID = "11111111-2222-3333-4444-555555555555"
TENANT = "https://contoso-admin.sharepoint.com"


class Failed(SystemExit):
    pass


def run(*argv: str, expect: int) -> str:
    """One command a reader would type, and the code it must return."""
    done = subprocess.run(
        [CONSOLE, *argv],
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "200"},
    )
    said = done.stdout + done.stderr
    if "Traceback" in said:
        raise Failed(
            f"`{CONSOLE} {' '.join(argv)}` printed a traceback on "
            f"{platform.system()}:\n{said}"
        )
    if done.returncode != expect:
        raise Failed(
            f"`{CONSOLE} {' '.join(argv)}` exited {done.returncode}, expected "
            f"{expect}, on {platform.system()}:\n{said}"
        )
    return said


def expect_in(said: str, fragment: str, what: str) -> None:
    if fragment.lower() not in said.lower():
        raise Failed(
            f"{what}: {fragment!r} was not in what a reader was shown:\n{said}"
        )


# The same reason the CLI reconfigures its own streams: this gate crashed on a
# Windows runner printing the tick that says the journey held. It had held.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    # WHICH EXECUTABLE, PRINTED FIRST AND ALWAYS. This resolves the console
    # script from PATH, because that is what a reader has — and on a developer
    # machine PATH frequently holds an installed release several versions
    # behind. A suite in this repository spent a whole session validating a
    # pipx copy of 1.0.0b4 without saying so, and turned into skips the day the
    # contract moved. A run against the wrong artefact is not preventable here;
    # being unable to see which one it was is.
    import shutil

    resolved = shutil.which(CONSOLE)
    if not resolved:
        raise Failed(
            f"`{CONSOLE}` is not on PATH. The package installs a console "
            f"script, and a reader who cannot type its name has not installed "
            f"it — which is the first thing this walk is for."
        )
    print(
        f"  {platform.system()} {platform.release()}, python {sys.version.split()[0]}"
    )
    print(f"  {resolved}")
    said_version = run("--version", expect=0).strip()
    print(f"  {said_version}")

    # AND IT HAS TO BE THIS TREE. Printing which executable was walked was half
    # the fix: the line was there, correct, and read as a pass while the walk
    # proved a release from before the change it was meant to check. Three rules
    # added on one afternoon were never in the artefact this reported green.
    #
    # The walk still goes through PATH, because that is what a reader has. What
    # changed is that a PATH copy older than the checkout stops the walk instead
    # of quietly standing in for it.
    tree = _tree_version()
    if tree and tree not in said_version:
        raise Failed(
            f"the console script on PATH is {said_version.split()[-1]} and this "
            f"checkout is {tree}. The walk would prove a build that does not "
            f"contain the change being checked. Reinstall it -- "
            f"`pip install -e .` in this repository -- and run the walk again."
        )

    said = run("doctor", expect=0)
    expect_in(said, "packaged content", "doctor names what shipped")

    # THE COMMAND THAT PUBLISHES WHAT THIS ENGINE CLAIMS, run against the
    # artefact somebody installed rather than against a checkout. It read a
    # register that was in no wheel and raised FileNotFoundError for every
    # installed engine, and this journey did not walk past it, so nothing said
    # so. A reader reaching for `capabilities` on a fresh install met a
    # traceback where the product's own account of itself should have been.
    catalogue = run("capabilities", expect=0)
    expect_in(catalogue, "Capabilities", "capabilities names what is collected")
    expect_in(catalogue, "Rules", "capabilities names the catalogue it carries")
    # The remedy is a command where a command exists, and a link where one does
    # not. Naming what is missing is half a diagnosis.
    if "PowerShell 7" in said and "not found" in said:
        expected = {"Darwin": "brew install", "Windows": "winget install"}.get(
            platform.system(), "aka.ms/powershell"
        )
        expect_in(said, expected, "the missing-PowerShell remedy")

    run("list-rules", expect=0)
    run("explain", "unknown", expect=0)

    # A refusal is exit 2 and one sentence, on every system.
    said = run("evaluate", "--evidence", "./no-such-file.json", expect=2)
    expect_in(said, "no such file", "a path that is not there")

    said = run("connect", "--client-id", "not-a-guid", "--tenant-url", TENANT, expect=2)
    expect_in(said, "not an application registration", "a malformed client id")

    said = run("connect", "--client-id", GUID, expect=2)
    expect_in(said, "an address to reach", "no address")

    # The project file, written and then read back from a subdirectory. This is
    # where `HOME` against `USERPROFILE` and a path separator would show.
    root = tempfile.mkdtemp(prefix="journey-")
    here = os.getcwd()
    try:
        os.chdir(root)
        said = run("setup", expect=0)
        expect_in(said, "Register-PnPEntraIDApp", "setup names how to get an identity")

        run("setup", "--client-id", GUID, "--tenant-url", TENANT, expect=0)
        if not os.path.isfile(os.path.join(root, "m365-governance.toml")):
            raise Failed("setup reported success and wrote no project file")

        deep = os.path.join(root, "evidence", "august")
        os.makedirs(deep)
        os.chdir(deep)
        said = run("run", "--dry-run", expect=0 if _has_powershell() else 2)
        expect_in(said, "m365-governance.toml", "the run says which file it read")
        expect_in(said, "not run", "the plan reports what it will not do")
    finally:
        os.chdir(here)

    print("  ✓ the journey holds on this machine")
    return 0


def _has_powershell() -> bool:
    import shutil

    return shutil.which("pwsh") is not None


if __name__ == "__main__":
    raise SystemExit(main())
