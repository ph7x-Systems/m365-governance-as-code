"""The live matrix is a record, and a record nothing checks is a draft.

`docs/COLLECTOR-LIVE-MATRIX.md` is named by `AGENTS.md` as where a collector's
live state is recorded, and by `docs/LIVE-VALIDATION.md` as what the states
mean. Nothing in this repository read it. It was maintained by hand, and both
things that happen to a hand-maintained record happened to it:

  * A live run corrected the `customization` collector -- an enum that returned
    `Unknown` where every fixture used a boolean, found by provoking the state
    in a tenant -- and no row was updated. The matrix still reads `not
    observed` in both live columns for that collector.
  * Two rows said `**none**, by decision` under *Rules it supports* after the
    decision had been narrowed and the rule written. `SPO-SCRIPT-001` and
    `CA-STATE-001` were both invisible to the document that exists to say
    which rules depend on which collector.

The second kind is the dangerous one, because the matrix answers *if it fails,
what becomes unknown?* and a row claiming no rules depends on it answers that
question with silence.

These tests do not check that a live run happened. They check that what the
manifest says and what the document says are the same thing, which is the part
a person cannot be relied on to notice.
"""

from pathlib import Path

import pytest

from m365_governance.collecting import SLICES

MATRIX = Path(__file__).resolve().parents[1] / "docs" / "COLLECTOR-LIVE-MATRIX.md"


@pytest.fixture(scope="module")
def rows():
    """Every collector row, as `name -> the cells after it`."""
    found = {}
    inside = False
    for line in MATRIX.read_text().splitlines():
        if line.startswith("## "):
            # The document explains the states further down, in tables whose
            # first cell is also a backticked name. Only the matrix is the
            # record; the rest is prose about it.
            inside = line.strip() == "## The matrix"
            continue
        if not inside or not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        found[cells[0].strip("`")] = cells[1:]
    return found


def test_every_collector_has_a_row(rows):
    assert set(rows) == set(SLICES), (
        "the matrix and the manifest must carry the same collectors; a "
        "collector with no row has no recorded live state at all"
    )


def test_the_status_column_is_the_state_the_manifest_publishes(rows):
    """The document does not get its own opinion about how proven a slice is.

    `Live` was made an enum precisely because five slices carried five
    different sentences and anything wanting the state had to interpret prose.
    A second hand-written table of the same sentences reintroduces exactly what
    that change removed.
    """
    wrong = {
        name: (cells[-1], SLICES[name].live.value)
        for name, cells in rows.items()
        if SLICES[name].live.value not in cells[-1]
    }

    assert not wrong, (
        "rows whose status disagrees with the capability manifest "
        f"(row, manifest): {wrong}"
    )


def test_a_collector_that_feeds_a_rule_does_not_say_none_by_decision(rows):
    """`none, by decision` is a real and defensible entry, and it expires.

    Both collectors that carried it had the decision narrowed rather than
    reversed -- Microsoft still publishes no normative conclusion about which
    Conditional Access policies an organisation should have, and this engine
    still refuses to invent one -- and a rule was written on the part that was
    never in dispute. The row kept the old sentence, so the document that says
    which rules break when a collector breaks said none of them do.
    """
    RULES = 4  # the `Rules it supports` column

    lying = [
        name
        for name, cells in rows.items()
        if SLICES[name].produces_findings and "by decision" in cells[RULES]
    ]

    assert not lying, (
        f"collectors that feed rules while their row claims none: {lying}. "
        "The matrix answers 'if it fails, what becomes unknown?' and this row "
        "answers it with silence."
    )
