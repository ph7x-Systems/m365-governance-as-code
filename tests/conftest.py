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
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


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
