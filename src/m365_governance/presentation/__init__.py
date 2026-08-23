"""The engine's presentation layer, and the rule that governs it.

    The presentation layer may compress, format or annotate a domain state.
    It may never strengthen it.

That rule is not enforced by review here. `symbols` declares the states in
strength order and the tests walk the orders, so a rendering that moves a state
up fails before it reaches anybody.

WHY THIS EXISTS AS A BOUNDARY. A domain object that knew a symbol, a colour or
a stream would make the terminal a second place where product meaning is
decided, and the terminal is where it is decided casually -- while somebody is
improving a table. The engine returns states; this turns states into lines.

WHAT IS DELIBERATELY ABSENT. No dependency. The decision to abstract
presentation from the domain and the decision to adopt a terminal library are
separate, and taking the second one implicitly while making the first is how a
public engine with two dependencies acquires a third that nobody chose.

    Decision:         presentation is abstracted from the domain
    Current backend:  plain text, standard library
    Deferred:         a terminal library may back this later, for terminal-only
                      enhancement, provided the stdout/stderr split and the
                      machine-output contracts are unchanged

Deferred is not rejected, and it is written here so that nobody reads
`no library today` as `a library is forbidden`.
"""

from __future__ import annotations

from .console import Presentation
from .symbols import (
    LADDER_STRENGTH,
    MARKS,
    NOT_ON_THE_SCALE,
    STAGE,
    STAGE_STRENGTH,
    legend,
    mark,
    rank,
    strip,
)

__all__ = [
    "LADDER_STRENGTH",
    "MARKS",
    "NOT_ON_THE_SCALE",
    "STAGE",
    "STAGE_STRENGTH",
    "Presentation",
    "legend",
    "mark",
    "rank",
    "strip",
]
