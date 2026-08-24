"""The map may describe a surface once, and may not invent anything.

A REGISTER OF THINGS NOBODY HAS BUILT ROTS FASTER THAN CODE. Nothing fails when
a candidate row is wrong: no test breaks, no collector misbehaves, and the row
keeps being read as evidence until somebody spends a week building against it.
So the checks here are the ones that would otherwise be nobody's job -- every
endpoint carries an authority, every Graph row has been put to the schema, and
no surface is claimed by both halves at once.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import capabilities  # noqa: E402

RULES = ROOT / "src" / "m365_governance" / "data" / "rules"
REGISTER = ROOT / "src" / "m365_governance" / "data" / "candidate-surfaces.json"

API_VERSIONS = {"v1.0", "beta", "powershell"}
IDENTITIES = {"application", "delegated", "both", "not-established"}
COSTS = {"single-call", "per-user", "per-site", "tenant-report"}


@pytest.fixture(scope="module")
def register() -> dict:
    return json.loads(REGISTER.read_text())


@pytest.fixture(scope="module")
def manifest() -> dict:
    return capabilities.manifest(RULES)


def surfaces(register: dict) -> list[dict]:
    return register["surfaces"]


def test_every_candidate_cites_a_first_party_page(register):
    """`Microsoft says` is not a citation and neither is a remembered endpoint."""
    for s in surfaces(register):
        authority = s["authority"]
        assert authority["url"].startswith("https://learn.microsoft.com/"), s["id"]
        assert authority["read_on"], s["id"]


def test_every_candidate_uses_the_declared_vocabularies(register):
    for s in surfaces(register):
        assert s["api_version"] in API_VERSIONS, s["id"]
        assert s["identity"] in IDENTITIES, s["id"]
        assert s["cost"] in COSTS, s["id"]


def test_a_least_privilege_is_named_or_declared_unestablished(register):
    """Empty is an omission. `not-established` is an answer, and it passes.

    Exchange publishes no per-parameter permission table for
    `Get-OrganizationConfig`, so anything written in that field would be
    invented -- which is how somebody ends up consenting to a scope they did
    not need.
    """
    for s in surfaces(register):
        assert s["least_privilege"], s["id"]


def test_no_surface_is_claimed_by_both_halves(register, manifest):
    """A collected surface leaves the register in the commit that collects it.

    `licensing-report-settings` was a candidate row for `GET /admin/reportSettings`
    while the licensing collector was already reading it -- from `/beta/`, which
    is how the duplicate was found. Two owners for one surface means two answers
    to `which version do we call`, and they had already diverged.
    """
    collected = {
        read.split("?")[0].replace("GET /v1.0/", "").replace("GET /beta/", "").rstrip("/")
        for c in manifest["capabilities"]
        for read in c["collector"]["reads"]
        if read.startswith("GET /")
    }
    for s in surfaces(register):
        if not s["endpoint"].startswith("GET /"):
            continue
        candidate = s["endpoint"].replace("GET /", "").split("?")[0].rstrip("/")
        assert candidate not in collected, (
            f"{s['id']} is a candidate for a surface the engine already reads"
        )


def test_every_graph_candidate_has_been_put_to_the_schema(register):
    """A prose page says what an endpoint is for; only the schema says it exists."""
    for s in surfaces(register):
        if s["api_version"] == "powershell":
            assert "schema_check" not in s, s["id"]
            continue
        check = s["schema_check"]
        assert s["api_version"] in check["present_in"], s["id"]
        assert check["checked_on"], s["id"]


def test_a_beta_row_says_so_in_its_limitation(register):
    """A beta dependency is a released product's problem, so it is written down."""
    for s in surfaces(register):
        if s["api_version"] == "beta":
            assert "beta" in s["limitation"].lower(), s["id"]


def test_no_candidate_row_carries_a_write(register):
    """This engine reads. A register that proposed a write would be proposing
    a different product, and the readiness gate would refuse the rule anyway."""
    for s in surfaces(register):
        head = s["endpoint"].split()[0]
        assert head in {"GET"} or head.startswith(("Get-", "Test-", "Measure-", "Export-")), (
            f"{s['id']} names something that is not a read: {s['endpoint']}"
        )


def test_the_written_map_is_current():
    """The document is generated, so a stale one is a lie with a timestamp."""
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "capability-map.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert done.returncode == 0, done.stdout + done.stderr
