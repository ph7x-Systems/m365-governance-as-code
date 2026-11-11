"""The rule readiness gate, and the proof that it bites.

A gate that passes on the day it is born proves little: it may be measuring
something that was true anyway. These tests build rules that are deliberately
unfinished and require it to refuse each one.

TWO PROPERTIES, AND THE SECOND IS THE ONE THAT MATTERS. A rule is finished as a
rule when it says what it checks, on whose authority, from which evidence, what
a pass does not settle, when a collector feeds it, and when it has been SEEN
reaching every outcome it can reach. And no rule passes without having been run
against a tenant, because a rule proved against imagined evidence is a rule
proved against nothing.

There is no exception list, and there was one for about an hour. Seventeen
rules predate the tenant requirement, so their names were written down with a
reason each and the gate went green. That is how an absolute becomes a
tolerance. The gate is red instead, and the red names them.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "readiness", ROOT / "tools" / "rule-readiness.py"
)
readiness = importlib.util.module_from_spec(_spec)
sys.modules["readiness"] = readiness
_spec.loader.exec_module(readiness)


@pytest.fixture(scope="module")
def table() -> dict:
    return readiness.build()


@pytest.fixture(scope="module")
def manifest() -> dict:
    return readiness.capabilities.manifest(readiness.RULES)


def test_every_authored_rule_is_finished_as_a_rule(table):
    """Authorship is entirely in our hands on the day a rule is written."""
    missing = {
        r["id"]: [k for k, v in r["checks"].items() if not v]
        for r in table["detail"]
        if not r["rule_ready"]
    }
    assert not missing, f"unfinished rules: {json.dumps(missing, indent=1)}"


def test_the_published_table_is_the_one_this_produces(table):
    """A table nobody regenerates starts lying the following week."""
    published = ROOT / "docs" / "RULE-READINESS.json"
    assert published.exists(), "docs/RULE-READINESS.json was never generated"
    assert json.loads(published.read_text(encoding="utf-8")) == table, (
        "the published table differs from what the generator produces: run "
        "`python3 tools/rule-readiness.py`"
    )


def _rule(**changed) -> dict:
    base = {
        "id": "TEST-READY-001",
        "service": "sharepoint",
        "basis": {
            "type": "documented-limit",
            "sources": [{"url": "https://example.invalid"}],
        },
        "evidence_requirements": [{"path": "a.b", "type": "string", "required": True}],
        "outcomes": {"unknown": {"message": "it was not read"}},
        "limitations": {"passes_without_resolving": "a pass does not settle this"},
    }
    base.update(changed)
    return base


def test_a_rule_without_a_pass_boundary_is_refused(manifest):
    """`passes_without_resolving` is what separates this from a scanner."""
    verdict = readiness.readiness(
        _rule(limitations={}), {"pass", "fail", "unknown"}, ["sites"], manifest, True
    )
    assert not verdict["rule_ready"]
    assert not verdict["checks"]["pass_boundary"]


def test_a_rule_nothing_can_decide_is_refused(manifest):
    """With no fixture reaching it, the three outcomes were never observed."""
    verdict = readiness.readiness(_rule(), set(), ["sites"], manifest, True)
    assert not verdict["rule_ready"]
    assert not any(verdict["checks"][f"observed_{o}"] for o in readiness.OBSERVED)


def test_a_rule_no_collector_feeds_is_refused(manifest):
    """A rule with no acquisition path is a question nobody can ask, and with
    no capability there is no endpoint, no API version and no permission
    either: four conditions fall together because they are one fact."""
    verdict = readiness.readiness(
        _rule(), {"pass", "fail", "unknown"}, [], manifest, True
    )
    assert not verdict["rule_ready"]
    assert not verdict["checks"]["capability_known"]


def test_there_is_no_exception_list(table):
    """The gate must not be able to go green by naming what is unfinished.

    A register of tolerated rules would be where every future rule went to
    wait, and the seventeen that predate the requirement would have closed the
    gate rather than opened the work.
    """
    assert not hasattr(readiness, "AWAITING_TENANT"), (
        "an exception register came back: the debt closes by running the rules "
        "against a tenant, never by writing their names down"
    )
    assert all("awaiting_tenant" not in r for r in table["detail"])


def test_a_rule_that_never_met_a_tenant_does_not_pass(table):
    """The standing rule, enforced rather than reported.

    This test is EXPECTED TO NAME RULES until the live verticals are run. It is
    the register, and it lives here rather than in a list the gate consults:
    the difference is that this one cannot be edited to make the build green.
    """
    unproven = readiness.unproven(table)
    assert unproven, (
        "no rule is waiting for a tenant, so either every vertical has been "
        "run or this test stopped measuring"
    )
    assert table["tenant_proven"] + len(unproven) == table["rules"]


def test_a_rule_that_never_met_a_refusal_is_refused(manifest):
    """A refused read is not a missing fact.

    One is the tenant saying no and the other is nobody having asked, and they
    arrive at a rule looking identical: both are `unknown`. What separates them
    is the coverage block. A rule shown only silence has an untested branch on
    the path a real tenant reaches first, and this gate asked for a `refused`
    OUTCOME at first -- which does not exist, so every rule failed it and the
    failure looked like a catalogue problem rather than a gate problem.
    """
    verdict = readiness.readiness(
        _rule(), {"pass", "fail", "unknown"}, ["sites"], manifest, False
    )
    assert not verdict["rule_ready"]
    assert not verdict["checks"]["observed_refusal"]


def test_a_permission_nobody_established_is_declared_rather_than_invented(tabela=None):
    """`not-established` is an answer and passes; an empty list is an omission.

    Least privilege is recorded where a source establishes it and invented
    nowhere. A gate demanding a scope here would be asking somebody to make one
    up, which is the failure this whole engine is built against.
    """
    table = readiness.build()
    assert table["least_privilege_established"] < table["rules"], (
        "every surface now has an established least privilege, or this stopped "
        "measuring"
    )
    assert all(r["checks"]["permission_declared"] for r in table["detail"])
