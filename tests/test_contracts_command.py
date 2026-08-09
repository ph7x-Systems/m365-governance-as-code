"""The contract bundle is a released artefact, obtainable without this clone.

R8's exact claim was that nothing could answer "is this bundle current?" by any
automated means: the engine could change `run.schema.json` and every consumer
gate stayed green, because the bundle existed only inside this repository and
the consumer's copy was whatever somebody last remembered to paste.

So the bundle ships in the wheel and `m365-governance contracts --out` writes
it. These tests are about the three things that made it unobtainable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "m365_governance" / "data"


def test_the_declared_contract_version_is_the_engine_s_own():
    """It was a frozen constant whose comment said it moved when a schema moved.

    It did not. `run`, `run-set` and `assessment` went from 2.0.0 to 3.0.0 and
    this stayed at 1.0.0 — so a consumer comparing it across a BREAKING change
    saw no change at all, which is the one question it exists to answer.
    """
    import m365_governance

    manifest = json.loads(
        (DATA / "generated" / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["contract_version"] == m365_governance.__version__


def test_the_archived_contracts_are_declared_in_the_manifest():
    """A contract with history, and not one that pretends its past never was.

    An installed engine that lacked them would refuse a document declaring an
    archived contract as UNKNOWN rather than as valid-and-unsupported, which
    are different sentences: one says the document is wrong, the other says
    this build cannot read it.
    """
    manifest = json.loads(
        (DATA / "generated" / "manifest.json").read_text(encoding="utf-8")
    )
    archived = [
        uri for uri, e in manifest["schemas"].items() if "archive/" in e["path"]
    ]

    assert archived, "the bundle declares no archived contract"
    for uri in archived:
        path = DATA / manifest["schemas"][uri]["path"]
        assert path.is_file()


def test_the_command_writes_a_bundle_a_consumer_can_vendor(tmp_path):
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "m365_governance.cli",
            "contracts",
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert done.returncode == 0, done.stderr

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemas"]

    # Every schema the manifest declares arrived, at the path it declares, and
    # claims the identity it is registered under.
    for uri, entry in manifest["schemas"].items():
        written = tmp_path / entry["path"]
        assert written.is_file(), f"{uri} is declared and was not written"
        assert json.loads(written.read_text(encoding="utf-8"))["$id"] == uri

    assert list((tmp_path / "csharp").glob("*.g.cs"))


def test_the_written_bundle_matches_the_one_in_this_repository(tmp_path):
    """Written from the installation, and identical to what is published here.

    If the two could differ, a consumer's bundle would depend on which of the
    two paths somebody happened to use.
    """
    subprocess.run(
        [
            sys.executable,
            "-m",
            "m365_governance.cli",
            "contracts",
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    here = json.loads(
        (DATA / "generated" / "manifest.json").read_text(encoding="utf-8")
    )
    there = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert here == there
    for entry in here["schemas"].values():
        assert (tmp_path / entry["path"]).read_bytes() == (
            DATA / entry["path"]
        ).read_bytes()


@pytest.mark.parametrize("directory", ["schemas", "generated"])
def test_the_wheel_would_carry_it(directory):
    """Declared in package-data, recursively.

    `schemas/*.json` matched six files and silently left the four archived
    contracts out. The release check compares the wheel against the tree; this
    is the cheaper statement of the same rule, next to the reason.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    if directory == "schemas":
        assert '"schemas/**/*.json"' in pyproject
        assert '"schemas/*.json"' not in pyproject
    else:
        assert '"generated/manifest.json"' in pyproject
        assert '"generated/csharp/*.g.cs"' in pyproject
