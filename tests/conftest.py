"""Shared paths and helpers.

Nothing here reaches a network or a tenant. The whole suite runs offline
against fixtures, which is the only way the engine can be tested at all: a
test that needs a tenant is a test that does not run.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

#: The product's content lives inside the package, so that an installed copy
#: carries it. The tests read the same files the package ships rather than a
#: second copy at the repository root: two copies would drift, and the one the
#: tests agreed with would be the one nobody installs.
DATA = ROOT / "src" / "m365_governance" / "data"
RULES = DATA / "rules"
FIXTURES = DATA / "fixtures" / "sharepoint"
ENTRA = DATA / "fixtures" / "entra"

#: Every workload's fixtures. One list so that a schema guard covers a new
#: workload the day it is added, rather than the day somebody remembers to
#: widen a glob that named one directory.
EVIDENCE_FIXTURES = sorted(
    path for folder in (FIXTURES, ENTRA) for path in folder.glob("*.json")
)
SCHEMAS = DATA / "schemas"
PROFILES = DATA / "profiles"
COLLECTORS = DATA / "collectors"


def rule(rule_id: str) -> dict:
    for path in sorted(RULES.rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("id") == rule_id:
            return data
    raise AssertionError(f"rule {rule_id} not found under {RULES}")


def evidence(name: str) -> dict:
    for folder in (FIXTURES, ENTRA):
        path = folder / f"{name}.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    # FileNotFoundError and not an assertion: a caller that deliberately asks
    # for a fixture that may not exist catches it, and an assertion would turn
    # that into a failure about the wrong thing.
    raise FileNotFoundError(f"no fixture {name}.json under {FIXTURES} or {ENTRA}")


def sabotage(document: dict, mutate) -> dict:
    """A deep copy with one thing broken. The original is never touched."""
    broken = copy.deepcopy(document)
    mutate(broken)
    return broken


@pytest.fixture
def list_rule() -> dict:
    return rule("SPO-LIST-001")


@pytest.fixture
def site_rule() -> dict:
    return rule("SPO-SITE-001")


# ── the suite cannot reach a tenant, and now it cannot pretend to ──────────
#
# THE DOCSTRING AT THE TOP OF THIS FILE SAID SO AND NOTHING ENFORCED IT.
#
# A test asserted that `collect` refuses a badly shaped `--output`. The guard it
# tested was removed when `--output` was given one meaning, so `main` ran the
# collector for real: PowerShell launched, `Connect-PnPOnline -Interactive`
# opened a browser, and the person running `pytest` was asked to sign in to
# whichever directory their browser was signed into. It named the client id
# from the test file, which is how it was found — after being met three times
# and blamed on the documentation.
#
# A promise in prose is not a property. This is the property: any test that
# tries to start the collector fails, naming itself, before a process exists.
#
# A test that needs the collector patches `_run` for itself, which is what the
# ones that mean to already do.
@pytest.fixture(autouse=True)
def _no_test_reaches_a_tenant(monkeypatch, request):
    """Refuse to start the shipped collector from inside the suite."""
    from m365_governance import collecting

    real = collecting.subprocess.Popen

    def guarded(argv, *rest, **named):
        # AT THE BOUNDARY WHERE A PROCESS IS BORN, and not on the function that
        # asks for one. The plumbing tests run `_run` against a harmless
        # command on purpose, and one of them replaces `Popen` itself to prove
        # that a missing `pwsh` arrives as an outcome. Guarding here lets both
        # keep working: a test that patches `Popen` after this fixture wins,
        # which is the right order.
        # THE ENTRY POINT, NOT THE DIRECTORY. `pwsh -File <collector>.ps1` is
        # the thing that connects; a test that imports a module inline to check
        # what a function emits reaches nothing, and refusing it would be this
        # guard forbidding the offline tests it exists to protect.
        parts = [str(part) for part in (argv or [])]
        entry = ""
        for flag in ("-File", "-file"):
            if flag in parts and parts.index(flag) + 1 < len(parts):
                entry = parts[parts.index(flag) + 1]
        if entry.endswith(".ps1") and (
            "data/collectors" in entry or "data\\collectors" in entry
        ):
            raise AssertionError(
                f"{request.node.nodeid} tried to start the shipped collector. "
                "No test may: the process authenticates, and on a machine with "
                "a browser it opens a sign-in against whatever directory is "
                "signed in. Patch `collecting._run` for this test, or assert on "
                "the refusal that should have happened before the process."
            )
        return real(argv, *rest, **named)

    monkeypatch.setattr(collecting.subprocess, "Popen", guarded)
