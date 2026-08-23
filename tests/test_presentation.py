"""The layer that renders truth, and the two ways it used to damage it.

ONE: IT STRENGTHENED STATES. A capability whose acquisition was never
attempted printed `live-validated`; a site rendered a value meaning *a read
produced evidence* as `read from a tenant, end to end`. Neither was a lie
anybody told on purpose -- both were a layer choosing a friendlier word than
the value it was handed. The rule is written in `presentation/__init__`:

    The presentation layer may compress, format or annotate a domain state.
    It may never strengthen it.

The tests below walk the declared strength orders so that the rule is a
property rather than a promise somebody remembers.

TWO: IT WROTE COMMENTARY TO STDOUT. Three places printed collection progress
with a bare `print`. A pipeline redirecting stdout is asking for the RESULT,
and every progress line landing there is corruption of somebody's data, found
later by a parser that failed on `sites: read`.
"""

from __future__ import annotations

import io
import json

import pytest

from m365_governance import presentation
from m365_governance.presentation import symbols


def _streams(**kwargs):
    out, err = io.StringIO(), io.StringIO()
    ui = presentation.Presentation(
        output=out, status=err, interactive=False, **kwargs
    )
    return ui, out, err


# ---------------------------------------------------------------------------
# it may never strengthen
# ---------------------------------------------------------------------------


def test_every_stage_state_has_exactly_one_mark_and_no_two_share_one():
    """A shared mark is a state pretending to be another one.

    If `not-attempted` and `proven` ever rendered the same, the strip would be
    unreadable in the one direction that matters -- a reader would take the
    stronger reading, because that is the reading people take.
    """
    marks = [symbols.STAGE[state] for state in symbols.STAGE]

    assert len(set(marks)) == len(marks), f"two stage states share a mark: {marks}"
    for state in (*symbols.STAGE_STRENGTH, "not-applicable"):
        assert state in symbols.STAGE, f"{state} has no mark and would render as `?`"


def test_a_state_outside_the_scale_is_refused_rather_than_defaulted():
    """A silent zero would make an unrecognised state compare as the weakest
    thing available. That is the right direction for a MARK and completely
    wrong for a comparison, which is why they are different functions."""
    with pytest.raises(ValueError):
        symbols.rank("brand-new-state", symbols.LADDER_STRENGTH)

    for outside in symbols.NOT_ON_THE_SCALE:
        with pytest.raises(ValueError):
            symbols.rank(outside, symbols.STAGE_STRENGTH)


def test_the_ladder_and_the_stages_agree_about_which_end_is_stronger():
    """The two scales are separate and must not drift apart: a capability
    cannot be `vertical-path-proven` while its stages say `not-attempted`, and
    the orders are what any check of that would be written against."""
    assert symbols.STAGE_STRENGTH[0] == "not-attempted"
    assert symbols.STAGE_STRENGTH[-1] == "proven"
    assert symbols.LADDER_STRENGTH[0] == "not-live-tested"
    assert symbols.LADDER_STRENGTH[-1] == "vertical-path-proven"

    assert symbols.rank("not-live-tested", symbols.LADDER_STRENGTH) < symbols.rank(
        "vertical-path-proven", symbols.LADDER_STRENGTH
    )


def test_an_unknown_stage_renders_weaker_than_every_state_it_could_have_been():
    """The direction of this error is chosen. A value this layer does not
    recognise must not borrow the appearance of one it does."""
    rendered = symbols.strip({"acquisition": "something-new"}, ("acquisition",))

    assert rendered == "?"
    assert rendered not in symbols.STAGE.values()


def test_partial_is_not_rendered_as_a_success():
    """THE FAILURE THIS PREVENTS IS A CONCLUSION, NOT AN AESTHETIC.

    A collection that returned some of what it asked for, shown as a tick,
    tells the reader the rules over it were decided on everything. It has its
    own mark for that reason.
    """
    ui, _, err = _streams()
    ui.step("sites")
    ui.partial("authentication methods")

    lines = err.getvalue().splitlines()
    assert lines[0].startswith(symbols.mark("ok"))
    assert lines[1].startswith(symbols.mark("partial"))
    assert symbols.mark("partial") != symbols.mark("ok")


# ---------------------------------------------------------------------------
# stdout is the result and nothing else
# ---------------------------------------------------------------------------


def test_progress_and_warnings_never_reach_the_stream_a_pipeline_captures():
    ui, out, err = _streams()

    ui.heading("Collection")
    ui.progress("Collecting sites...")
    ui.step("sites", detail="183 resources", elapsed=4.8)
    ui.partial("authentication methods", detail="partial")
    ui.skipped("privileged eligibility")
    ui.warning("a surface answered slowly")
    ui.failure("the certificate could not be opened")

    assert out.getvalue() == "", (
        "something a person reads while waiting reached the stream a pipeline "
        f"captures: {out.getvalue()!r}"
    )
    assert "Collecting sites..." in err.getvalue()


def test_a_result_redirected_to_a_file_parses_with_nothing_else_in_it():
    """The whole point, as a pipeline experiences it."""
    ui, out, err = _streams()

    ui.progress("Collecting sites...")
    ui.emit(json.dumps({"assessment": {"rules": 33}}))
    ui.step("done")

    assert json.loads(out.getvalue()) == {"assessment": {"rules": 33}}
    assert err.getvalue() != ""


def test_quiet_silences_the_commentary_and_never_the_answer():
    """For cron, where a successful run should say nothing. A caller that
    asked for an answer is not asking for it less loudly."""
    ui, out, err = _streams(quiet=True)

    ui.heading("Collection")
    ui.step("sites")
    ui.progress("still going")
    ui.emit("the answer")
    ui.failure("the certificate could not be opened")

    assert out.getvalue().strip() == "the answer"
    assert "sites" not in err.getvalue()
    assert "certificate" in err.getvalue(), "a failure is never silenced"


def test_no_control_sequences_are_written_when_nobody_is_watching():
    """A redirected run gets the same lines, without a spinner's cursor
    movement embedded in a log file."""
    ui, out, err = _streams()

    ui.progress("Connecting to Microsoft 365...")
    ui.step("connected", elapsed=1.8)

    assert "\x1b" not in err.getvalue() + out.getvalue()
    assert "\r" not in err.getvalue() + out.getvalue()


def test_interactivity_is_decided_from_the_stream_a_person_is_watching():
    """Read from STATUS and not from OUTPUT. A run whose result is redirected
    to a file is still being watched by somebody, and testing the wrong stream
    turns their terminal silent."""

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    ui = presentation.Presentation(output=io.StringIO(), status=Terminal())

    assert ui.interactive is True


def test_the_marks_have_an_ascii_alphabet_for_terminals_that_mangle_the_rest():
    ui, _, err = _streams(ascii_only=True)
    ui.step("sites")
    ui.partial("authentication methods")

    printed = err.getvalue()
    assert "[ok]" in printed and "[partial]" in printed
    assert printed.isascii()


# ---------------------------------------------------------------------------
# the boundary itself
# ---------------------------------------------------------------------------


def test_the_domain_never_learns_a_symbol_a_stream_or_a_colour():
    """WHY THIS IS A BOUNDARY AND NOT A HELPER MODULE.

    A domain object that knew a mark would make the terminal a second place
    where product meaning is decided, and the terminal is where it gets
    decided casually -- while somebody is improving a table.
    """
    import pathlib

    from m365_governance import engine, graph, results

    for module in (engine, results, graph):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in ("\\x1b[", "presentation"):
            assert forbidden not in source, (
                f"{module.__name__} knows about presentation: {forbidden!r}"
            )


def test_no_dependency_was_taken_while_making_this_boundary():
    """The decision to abstract presentation and the decision to adopt a
    terminal library are separate. Taking the second implicitly while making
    the first is how an engine with two dependencies acquires a third nobody
    chose. Deferred is recorded in `presentation/__init__`, and deferred is
    not rejected."""
    import pathlib

    for name in ("__init__", "console", "symbols"):
        source = pathlib.Path(
            presentation.__file__
        ).parent.joinpath(f"{name}.py").read_text(encoding="utf-8")
        for library in ("import rich", "from rich", "import click", "import typer"):
            assert library not in source, f"{name}.py took a dependency: {library}"


def test_the_installed_command_keeps_its_streams_apart(tmp_path):
    """THE TEST AS A PIPELINE EXPERIENCES IT, through a real process.

    Everything above substitutes streams in this process, which proves the
    layer. This proves the wiring: a command run the way a scheduled job runs
    it, with stdout redirected to a file, and the file parsed.
    """
    import subprocess
    import sys

    finished = subprocess.run(
        [
            sys.executable,
            "-c",
            "from m365_governance import cli; cli.main(['capabilities','--format','json'])",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    document = json.loads(finished.stdout)
    assert document["capabilities"], "stdout did not carry the requested payload"
    assert finished.stderr == "", (
        f"commentary reached the captured stream: {finished.stderr!r}"
    )


def test_a_plan_is_a_result_and_belongs_on_stdout(tmp_path):
    """`--dry-run` answers a question -- what would this do -- so its answer is
    the payload, not commentary. The distinction is what the caller ASKED for,
    never how conversational the text looks."""
    import subprocess
    import sys

    finished = subprocess.run(
        [
            sys.executable,
            "-c",
            "from m365_governance import cli; import sys; sys.exit(cli.main("
            "['collect','tenant-governance','--tenant-url',"
            "'https://contoso-admin.sharepoint.com','--client-id',"
            "'7c9f2a41-3b6d-4e58-9a02-cf51d8e7b3aa','--dry-run','--output',"
            f"'{tmp_path}']))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "would read" in finished.stdout
    assert finished.stderr == ""
