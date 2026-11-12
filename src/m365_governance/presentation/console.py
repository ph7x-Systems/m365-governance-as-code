"""Where output goes, decided once, so nobody has to remember.

THE CONTRACT, AND IT IS NOT A STYLE PREFERENCE:

    human progress, warnings and diagnostics  ->  stderr
    machine output and the requested payload  ->  stdout

A pipeline redirecting stdout to a file is asking for the RESULT. Every line of
progress that lands there is corruption of somebody's data, discovered later by
a `jq` that fails on a line saying `Collecting sites...`.

This engine was doing it: three places printed collection progress with a bare
`print`, which is stdout. The fix that lasts is not finding those three. It is
that there is no longer a function here that writes to a stream the caller did
not name -- `emit` goes to stdout because it carries a result, and everything
else goes to stderr because it does not.

NO SPINNER, AND NOT YET BY OMISSION. A spinner writes control sequences, which
belong in a terminal and nowhere else, and the first thing this layer has to
earn is not lying. Animation comes after, on top of a surface that is already
honest and already keeps pipes clean.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TextIO

from . import symbols


@dataclass
class Presentation:
    """The engine's one voice, holding both streams and choosing neither.

    A caller says what a line IS -- a result, a step, a warning -- and this
    decides where it goes. A caller that could pass a stream would eventually
    pass the wrong one, on a Friday, in a branch nobody tested.
    """

    #: The result. Redirect this and you have the answer and nothing else.
    output: TextIO = sys.stdout

    #: Everything a person reads while waiting. Never part of the answer.
    status: TextIO = sys.stderr

    #: Whether a person is watching. Read from the STATUS stream: a run whose
    #: output is redirected to a file is still being watched by somebody, and
    #: testing the wrong stream turns their terminal silent.
    interactive: bool | None = None

    #: Marks in ASCII, for a terminal or a log that mangles the rest.
    ascii_only: bool = False

    #: Print nothing but failures. For cron, where a successful run should say
    #: nothing at all.
    quiet: bool = False

    def __post_init__(self) -> None:
        if self.interactive is None:
            self.interactive = _is_terminal(self.status)
        if os.environ.get("M365_GOVERNANCE_ASCII"):
            self.ascii_only = True

    # -- the result -------------------------------------------------------

    def emit(self, text: str) -> None:
        """A result, to stdout, unchanged.

        THE ONLY FUNCTION HERE THAT WRITES TO STDOUT, and it neither decorates
        nor annotates. `--quiet` does not silence it: quiet is about the
        commentary, and a caller that asked for an answer is not asking less
        loudly.
        """
        print(text, file=self.output, flush=True)

    # -- everything else --------------------------------------------------

    def step(
        self, text: str, *, detail: str = "", elapsed: float | None = None
    ) -> None:
        """One thing that finished, and how it went."""
        self._status(
            symbols.mark("ok", ascii_only=self.ascii_only), text, detail, elapsed
        )

    def partial(
        self, text: str, *, detail: str = "", elapsed: float | None = None
    ) -> None:
        """One thing that partly happened, WHICH IS NOT A WEAK SUCCESS.

        A capability that returned some of what it was asked for has its own
        mark, because rendering it as a tick is the exact failure this layer
        exists to prevent: the reader concludes the collection was complete and
        the rules over it were decided on everything.
        """
        self._status(
            symbols.mark("partial", ascii_only=self.ascii_only), text, detail, elapsed
        )

    def skipped(self, text: str, *, detail: str = "") -> None:
        """Something that was not attempted, said as not attempted."""
        self._status(symbols.mark("skipped", ascii_only=self.ascii_only), text, detail)

    def warning(self, text: str, *, detail: str = "") -> None:
        self._status(symbols.mark("warning", ascii_only=self.ascii_only), text, detail)

    def failure(self, text: str, *, detail: str = "") -> None:
        """A failure, which `--quiet` never silences."""
        self._write(
            _line(
                symbols.mark("failed", ascii_only=self.ascii_only), text, detail, None
            )
        )

    def info(self, text: str) -> None:
        self._status("", text, "", None)

    def heading(self, text: str) -> None:
        if self.quiet:
            return
        self._write("")
        self._write(text)

    def progress(self, text: str) -> None:
        """Something under way, whose end is not yet known.

        No control sequences, in a terminal or out of it. When this layer grows
        a spinner it will grow it here, behind `interactive`, and a redirected
        run will keep getting exactly this line.
        """
        self._status(symbols.mark("info", ascii_only=self.ascii_only), text, "", None)

    # -- the plumbing -----------------------------------------------------

    def _status(
        self, sign: str, text: str, detail: str, elapsed: float | None = None
    ) -> None:
        if self.quiet:
            return
        self._write(_line(sign, text, detail, elapsed))

    def _write(self, line: str) -> None:
        print(line, file=self.status, flush=True)


def _line(sign: str, text: str, detail: str, elapsed: float | None) -> str:
    """One line, laid out so it survives eighty columns.

    The detail and the timing are appended rather than placed in columns: a
    column layout that fits a wide terminal wraps into nonsense in a narrow
    one, and this output is read in CI logs more often than in a window
    somebody sized.
    """
    parts = [part for part in (sign, text) if part]
    if detail:
        parts.append(f"· {detail}")
    if elapsed is not None:
        parts.append(f"· {elapsed:.1f}s")
    return " ".join(parts)


def _is_terminal(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        # A stream that was closed, or something standing in for one. Assume
        # nobody is watching: the cost of being wrong is a missing flourish,
        # and the cost of the opposite is control sequences in a log file.
        return False
