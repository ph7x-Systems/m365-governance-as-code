"""The table in ARCHITECTURE.md, executed.

That document publishes which operators can be decided from partial evidence
and on which side. Until now most of the table had never run: coverage put
the bounded comparison at 86 per cent, and the missing lines were nearly all
of it.

A documented claim that nothing executes is a claim that drifts. These tests
are the table, one case per cell, written so that changing the engine without
changing the document goes red.
"""

from __future__ import annotations

import pytest

from m365_governance.engine import Resolved, compare


def bounded(lower: int | None, upper: int | None = None) -> Resolved:
    return Resolved(path="x", kind="bounded", lower=lower, upper=upper, state="partial")


def exact(value) -> Resolved:
    return Resolved(path="x", kind="exact", value=value, state="observed")


# ---------------------------------------------------------------------------
# "Without an upper bound the engine can prove `pass` and can never prove
# `fail`." The example in the document: three owners, one unexpanded group.
# ---------------------------------------------------------------------------


def test_the_worked_example_from_the_document():
    at_least_three = bounded(lower=3)
    assert compare(at_least_three, "greater-than-or-equal", 2) is True
    assert compare(at_least_three, "greater-than-or-equal", 5) is None


@pytest.mark.parametrize(
    "operator,lower,upper,value,expected",
    [
        # greater-than: the lower bound settles a pass; only an upper bound
        # can settle a fail.
        ("greater-than", 10, None, 5, True),
        ("greater-than", 10, None, 10, None),
        ("greater-than", 3, None, 5, None),
        ("greater-than", 3, 4, 5, False),
        # greater-than-or-equal
        ("greater-than-or-equal", 5, None, 5, True),
        ("greater-than-or-equal", 4, None, 5, None),
        ("greater-than-or-equal", 4, 4, 5, False),
        # less-than: the mirror. Only an upper bound settles a pass.
        ("less-than", 1, None, 5, None),
        ("less-than", 1, 4, 5, True),
        ("less-than", 5, None, 5, False),
        ("less-than", 9, None, 5, False),
        # less-than-or-equal
        ("less-than-or-equal", 1, 5, 5, True),
        ("less-than-or-equal", 6, None, 5, False),
        ("less-than-or-equal", 1, None, 5, None),
        # exists: one instance known proves it.
        ("exists", 1, None, None, True),
        ("exists", 0, None, None, None),
        ("not-exists", 1, None, None, False),
        ("not-exists", 0, None, None, None),
        # equals and not-equals: never, from a bound alone.
        ("equals", 5, 5, 5, None),
        ("not-equals", 5, 5, 4, None),
        # membership needs the members, which a numeric bound does not carry.
        ("contains", 3, None, "x", None),
        ("in", 3, None, ["x"], None),
    ],
)
def test_the_bounded_table(operator, lower, upper, value, expected):
    assert compare(bounded(lower, upper), operator, value) is expected


def test_a_bound_of_none_decides_nothing():
    """An aggregate in `partial` state with no minimum_count at all."""
    for operator in ("greater-than", "less-than", "equals"):
        assert compare(bounded(None), operator, 5) is None


# ---------------------------------------------------------------------------
# exists and not-exists on an observed value, which had never run either
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "operator,value,expected",
    [
        ("exists", 0, True),
        ("exists", "", True),
        ("exists", [], True),
        ("exists", None, False),
        ("not-exists", None, True),
        ("not-exists", 0, False),
    ],
)
def test_exists_reads_presence_and_not_truth(operator, value, expected):
    """`exists` asks whether a value was observed, never whether it is
    truthy. A collected zero exists; that is the whole point of collecting."""
    assert compare(exact(value), operator, None) is expected


def test_an_operator_that_cannot_apply_to_the_value_is_undecided():
    """Comparing a string against a number is not False. It is a comparison
    the evidence does not settle, and returning False would be an answer."""
    assert compare(exact("many"), "greater-than", 100) is None
    assert compare(exact(5), "contains", "x") is None


def test_an_unknown_operator_never_decides():
    """The schema rejects one, so this is the second line of defence."""
    assert compare(exact(5), "matches", 5) is None
