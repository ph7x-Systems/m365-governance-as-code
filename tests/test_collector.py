"""The collector has no write path, and does not conclude.

A static check rather than a run: there is no tenant in CI, and there never
will be. What can be proved offline is that the script cannot change anything
and does not smuggle a judgement into the evidence.
"""

from __future__ import annotations

import re

from conftest import ROOT

COLLECTOR = ROOT / "collectors" / "powershell" / "sharepoint" / "Get-SpoEvidence.ps1"

#: Verb-Noun forms that change something. Matched on the PnP and Graph command
#: surfaces, where a mutation is always one of these verbs.
MUTATING = re.compile(
    r"\b(Set|New|Remove|Add|Update|Grant|Revoke|Reset|Restore|Move|Rename|"
    r"Disable|Enable|Submit|Publish)-(PnP|Mg|SPO)\w+",
    re.IGNORECASE,
)

#: Fields that presume a rule. A collector that returns any of these has moved
#: the judgement out of a reviewable diff and into code.
CONCLUSIONS = (
    "is_compliant",
    "isCompliant",
    "risk",
    "score",
    "recommended_action",
    "recommendation",
    "severity",
)


def source() -> str:
    return COLLECTOR.read_text(encoding="utf-8")


def test_the_collector_exists():
    assert COLLECTOR.is_file()


def test_the_collector_has_no_write_path():
    found = MUTATING.findall(source())
    assert not found, f"mutating cmdlet in a read-only collector: {found}"


def test_the_collector_returns_no_conclusion():
    body = source()
    # Skip the comment block, which names these fields precisely to forbid them.
    code = body.split("#>", 1)[1]
    offenders = [word for word in CONCLUSIONS if word in code]
    assert not offenders, f"a collector may not decide: {offenders}"


def test_the_collector_records_identity_kind():
    """Without it, a delegated run reads as a tenant-wide statement."""
    assert "identity_kind" in source()


def test_the_collector_never_returns_an_empty_list_on_failure():
    """Every failure path must produce a state and a reason, not `@()`."""
    code = source().split("#>", 1)[1]
    assert "New-Unavailable" in code
    assert re.search(r"catch\s*\{[^}]*Resolve-FailureState", code, re.DOTALL)


def test_group_expansion_is_declared_incomplete_rather_than_guessed():
    code = source()
    assert "not-attempted" in code
    assert "minimum_count" in code
