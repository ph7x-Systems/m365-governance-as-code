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

CONSOLE = "m365-governance"
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
    print(f"  {run('--version', expect=0).strip()}")

    said = run("doctor", expect=0)
    expect_in(said, "packaged content", "doctor names what shipped")
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
