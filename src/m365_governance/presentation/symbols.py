"""What a state looks like, and the guarantee that looking cannot change it.

THE RULE THIS FILE EXISTS TO MAKE STRUCTURAL:

    The presentation layer may compress, format or annotate a domain state.
    It may never strengthen it.

Written as a sentence it is a promise, and a promise is what somebody breaks
while making a table prettier. So the states are declared in STRENGTH ORDER
and the marks are declared against them, and a test walks both: a rendering
that moved a state up the order, or that gave two states of different strength
the same mark, fails before it reaches anybody.

The failure it prevents is specific and has happened here twice. A capability
whose acquisition was never attempted showed as `live-validated`; a site
rendered a contract value meaning *a read produced evidence* as `read from a
tenant, end to end`. Neither was a lie anybody told on purpose. Both were a
layer choosing a friendlier word than the value it was given.

CHARACTERS AND NOT COLOUR. A terminal without it, a log, a screenshot and a
paste into an issue all have to carry the same meaning. Colour may reinforce
what a character already says; it may never be the only thing carrying it.
"""

from __future__ import annotations

#: Every stage state a capability's proof can hold, WEAKEST FIRST.
#:
#: The order is the product's, not this module's: it is what `not-attempted`
#: being weaker than `attempted` means. `not-applicable` sits outside the
#: scale, because a stage that does not exist for a capability is not a weak
#: stage -- see NOT_ON_THE_SCALE.
STAGE_STRENGTH = (
    "not-attempted",
    "refused",
    "attempted",
    "proven",
)

#: Every proof state a capability can hold, WEAKEST FIRST.
LADDER_STRENGTH = (
    "not-live-tested",
    "acquisition-attempted",
    "positive-acquisition-observed",
    "vertical-path-proven",
)

#: States that are not weaker or stronger than anything, and must never be
#: compared with the scale. A stage that does not apply is a different kind of
#: statement from a stage that was not reached.
NOT_ON_THE_SCALE = ("not-applicable", "not-established")

#: One character per stage state. Unicode adds nothing here: these are already
#: the plainest marks available, and a collector's proof strip is read in logs
#: more often than in a terminal.
STAGE = {
    "proven": "+",
    "refused": "x",
    "attempted": "~",
    "not-attempted": ".",
    "not-applicable": "-",
}

#: The marks a line of output uses, in the two alphabets a terminal may have.
#: A mark carries a meaning, never a mood: `PARTIAL` is not a weak success.
MARKS = {
    "ok": ("✓", "[ok]"),
    "failed": ("✗", "[fail]"),
    "warning": ("!", "[warn]"),
    "partial": ("◐", "[partial]"),
    "unknown": ("?", "[unknown]"),
    "skipped": ("–", "[skipped]"),
    "info": ("→", "[info]"),
}


def mark(name: str, *, ascii_only: bool = False) -> str:
    """One mark, in whichever alphabet the caller can render."""
    unicode_mark, ascii_mark = MARKS[name]
    return ascii_mark if ascii_only else unicode_mark


def strip(stages: dict[str, str], order: tuple[str, ...]) -> str:
    """A capability's stages as one character each, in dependency order.

    A stage this module has no mark for renders as `?`, which is weaker than
    every real state. An unknown value must never borrow the appearance of a
    known one, and the direction of that error is chosen deliberately.
    """
    return "".join(STAGE.get(stages.get(name, "not-attempted"), "?") for name in order)


def legend(*, ascii_only: bool = False) -> str:
    """What the marks mean, printed beside the thing that uses them.

    A reader who has to remember which column was which is a reader who will
    read it as whichever answer they were expecting.
    """
    del ascii_only  # the stage marks are the same in both alphabets
    return "  ".join(f"{sign} {name}" for name, sign in STAGE.items())


def rank(state: str, scale: tuple[str, ...]) -> int:
    """Where a state sits on its scale, for anything that must not move it.

    Raises for a state outside the scale rather than returning a default: a
    silent `0` would make an unrecognised state render as the weakest thing
    available, which is the right direction for a MARK and the wrong thing
    entirely for a comparison.
    """
    if state not in scale:
        raise ValueError(f"{state!r} is not on this scale: {scale}")
    return scale.index(state)
