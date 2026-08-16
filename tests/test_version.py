"""One version, read rather than written down twice.

`__version__` used to be a literal in `m365_governance/__init__.py`, beside the
one in `pyproject.toml`. Releasing 1.0.0b2 bumped the packaging version and
left the literal at 1.0.0b1: the wheel was named for one version and the
program answered with another.

The naming half is cosmetic. The other half is not. This value travels into
every assessment as `engine_version`, so an assessment produced by one build
stated that a different build had decided it. The engine version is part of the
canonical content the digest is taken over, so the digest was honest about its
content and the content was not honest about what made it. In an engine whose
whole claim is that a conclusion can be traced back to what produced it, a
version that lies is not a typo.

Nothing caught it. The publish workflow compares the built filename to the
release tag, which agreed; the drift was between the filename and the running
program, and no gate looked there.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

from m365_governance import __version__

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _packaged_version() -> str:
    """The version in pyproject.toml, read without a TOML parser.

    Deliberately literal. This file exists to compare two sources, and reading
    both through the same library would put them in agreement by construction.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert m, "pyproject.toml declares no version"
    return m.group(1)


def test_the_program_reports_the_version_it_was_packaged_as():
    packaged = _packaged_version()
    assert __version__ == packaged, (
        f"the package declares {packaged!r} and the program answers "
        f"{__version__!r}. This is the value that goes into `engine_version` "
        f"on every assessment: when they differ, a document states that a "
        f"different build decided it."
    )


def test_the_command_line_reports_the_same_version():
    """Through the path a user takes, not through an import."""
    r = subprocess.run(
        [sys.executable, "-m", "m365_governance.cli", "--version"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == _packaged_version(), (
        f"`--version` answered {r.stdout.strip()!r} and the package declares "
        f"{_packaged_version()!r}"
    )


def test_the_fallback_never_passes_for_a_real_version():
    """With no distribution to ask, `__version__` falls back. That fallback
    must not read as a released version: `0.0.0+unknown` in a report is an
    admission, and an admission is what it should be."""
    if __version__ == "0.0.0+unknown":
        pytest.fail(
            "the package is not installed, so `__version__` is the fallback. "
            "Run `pip install -e .` before the suite: an assessment produced "
            "this way does not say which engine decided it."
        )
