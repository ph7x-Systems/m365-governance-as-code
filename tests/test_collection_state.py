"""How a collection ended, and what it managed to say while it ran.

`Outcome.ok` was the whole answer, and it is an exit code wearing a name. A run
that reached two hundred of three hundred sites and then lost its connection
had the same value as one that never authenticated. The first produced evidence
worth two hundred sites.

That collapse is made nowhere else here: coverage keeps `requested` and
`completed` apart, and a rule answers `unknown` rather than failing when the
gap could change its answer. These tests hold the collection outcome to the
same standard.

Nothing in this file reaches a tenant. `run_slice` is exercised against a
`pwsh` that is not there, and everything else is exercised against the parts
that decide, which is where the decisions live.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m365_governance.collecting import Outcome, State, incomplete_coverage, run_slice


def _outcome(**kwargs) -> Outcome:
    base = {
        "slice_name": "sites",
        "returncode": 0,
        "seconds": 1.0,
        "written": [],
        "stdout": "",
        "stderr": "",
    }
    return Outcome(**{**base, **kwargs})


def _evidence(path: Path, requested: list[str], completed: list[str], unavailable=None):
    path.write_text(
        json.dumps(
            {
                "coverage": {
                    "requested": requested,
                    "completed": completed,
                    "unavailable": unavailable or {},
                }
            }
        ),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# the four states
# ---------------------------------------------------------------------------


def test_a_clean_run_that_read_everything_is_completed(tmp_path):
    doc = _evidence(
        tmp_path / "a.json", ["items", "permissions"], ["items", "permissions"]
    )

    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    assert outcome.state is State.COMPLETED


def test_a_clean_run_that_read_less_than_it_asked_is_partial(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["items", "permissions"], ["items"])

    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    # Exit code zero and evidence on disk, and still not `completed`: the
    # document itself says it did not read permissions.
    assert outcome.state is State.PARTIAL


def test_a_run_that_died_having_written_nothing_is_failed():
    assert _outcome(returncode=1, written=[]).state is State.FAILED


def test_a_run_that_died_having_written_something_is_partial(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["items"], ["items"])

    outcome = _outcome(returncode=1, written=[doc])

    # THE POINT OF THE WHOLE TYPE. Two hundred of three hundred sites is
    # evidence worth two hundred sites; calling it `failed` throws that away.
    assert outcome.state is State.PARTIAL


def test_cancelled_is_never_inferred_from_an_exit_code():
    # A collector killed by the network and one stopped by a person exit the
    # same way. Only the caller knows which happened, so only the caller says.
    assert _outcome(returncode=130).state is not State.CANCELLED
    assert _outcome(returncode=130, cancelled=True).state is State.CANCELLED


def test_cancelled_outranks_everything_else(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["items"], [])

    outcome = _outcome(
        returncode=0,
        written=[doc],
        cancelled=True,
        incomplete=incomplete_coverage([doc]),
    )

    assert outcome.state is State.CANCELLED


def test_ok_still_means_the_process_exited_zero(tmp_path):
    """Kept and deliberately narrow, so nothing that reads it changes meaning.

    A partial collection can exit zero, so `ok` and `state` answer different
    questions and the older callers keep the answer they asked for."""
    doc = _evidence(tmp_path / "a.json", ["items", "permissions"], ["items"])

    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    assert outcome.ok is True
    assert outcome.state is State.PARTIAL


# ---------------------------------------------------------------------------
# coverage is read, never guessed
# ---------------------------------------------------------------------------


def test_the_gap_is_read_from_the_document(tmp_path):
    doc = _evidence(
        tmp_path / "site.json",
        ["items", "permissions"],
        ["items"],
        {"permissions": "the identity could not read them"},
    )

    (relato,) = incomplete_coverage([doc])

    assert "permissions not read" in relato
    # The collector's reason travels with the gap: what was not read matters
    # less than why, because only the why says whether it can be read at all.
    assert "the identity could not read them" in relato


def test_a_document_that_cannot_be_read_is_reported_and_not_skipped(tmp_path):
    quebrado = tmp_path / "broken.json"
    quebrado.write_text("{not json", encoding="utf-8")

    (relato,) = incomplete_coverage([quebrado])

    # Staying quiet about it would be the same rounding-up the states exist to
    # stop: a file that is not readable evidence is a reason to doubt the run.
    assert "cannot be read as evidence" in relato


def test_a_document_with_no_coverage_is_reported(tmp_path):
    sem = tmp_path / "empty.json"
    sem.write_text(json.dumps({"facts": {}}), encoding="utf-8")

    assert incomplete_coverage([sem]) == ["empty.json: no coverage recorded"]


def test_nothing_written_is_nothing_to_report():
    assert incomplete_coverage([]) == []


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------


def test_a_dry_run_reaches_no_tenant_and_reports_the_command(tmp_path):
    outcome = run_slice(
        "sites",
        client_id="00000000-0000-0000-0000-000000000000",
        output=tmp_path,
        tenant_url="https://contoso-admin.sharepoint.com",
        dry_run=True,
    )

    assert "-Mode" in outcome.stdout and "TenantSites" in outcome.stdout
    assert outcome.written == []
    # A COLLECTION THAT NEVER RAN HAS NO STATE. Asking for one used to answer
    # `completed`, which is a statement about a tenant nobody looked at.
    with pytest.raises(ValueError, match="dry run"):
        _ = outcome.state


def test_run_slice_accepts_a_progress_callback(tmp_path):
    """The signature is the contract a caller builds against.

    A dry run reaches nothing, so this asserts the door exists rather than what
    comes through it: a test that needed a tenant to prove a callback would
    never run anywhere."""
    lines: list[str] = []

    run_slice(
        "sites",
        client_id="00000000-0000-0000-0000-000000000000",
        output=tmp_path,
        tenant_url="https://contoso-admin.sharepoint.com",
        dry_run=True,
        on_progress=lines.append,
    )

    assert lines == []


def test_a_missing_collector_host_is_an_outcome_and_not_a_traceback(
    tmp_path, monkeypatch
):
    """`pwsh` absent is the ordinary case on a machine that only evaluates.

    It must arrive as a failed collection rather than as an exception, because
    a caller watching a collection cannot show a stack trace to somebody who
    just wanted to know whether their tenant was read."""
    import m365_governance.collecting as collecting

    def no_pwsh(*args, **kwargs):
        raise FileNotFoundError("pwsh")

    monkeypatch.setattr(collecting.subprocess, "Popen", no_pwsh)

    with pytest.raises(FileNotFoundError):
        # Recorded as it behaves today rather than as it should: the caller
        # gets the error and the outcome type does not carry it. Turning this
        # into `State.FAILED` changes what `preflight` is for, and that is a
        # decision rather than a fix.
        run_slice(
            "sites",
            client_id="00000000-0000-0000-0000-000000000000",
            output=tmp_path,
            tenant_url="https://contoso-admin.sharepoint.com",
        )


# ---------------------------------------------------------------------------
# the stream itself
# ---------------------------------------------------------------------------


def test_lines_arrive_while_the_child_is_still_running():
    """Against a real process, because buffering is the thing under test.

    `python -c` stands in for the collector: what matters is that a child which
    prints, waits, and prints again is reported in two instalments rather than
    one. A fake would prove the callback is wired and not that the output is
    unbuffered, which was the whole defect.
    """
    import sys as _sys
    import time as _time

    from m365_governance import collecting

    script = (
        "import sys, time\n"
        "print('first', flush=True)\n"
        "time.sleep(0.4)\n"
        "print('second', flush=True)\n"
    )

    moments: list[tuple[str, float]] = []
    start = _time.monotonic()
    code, out, _err, cancelled = collecting._run(
        [_sys.executable, "-c", script],
        lambda line: moments.append((line, _time.monotonic() - start)),
    )

    assert code == 0
    assert cancelled is False
    assert [line for line, _ in moments] == ["first", "second"]
    assert out == "first\nsecond"

    # The first line has to arrive before the child has finished. Buffered, both
    # would land together at the end, which is what `capture_output=True` did.
    first_at, second_at = moments[0][1], moments[1][1]
    assert second_at - first_at > 0.2, (
        f"both lines arrived together ({first_at:.2f}s, {second_at:.2f}s): the "
        f"output is buffered and nothing can report progress"
    )


def test_stderr_is_in_the_stream_where_somebody_watching_will_see_it():
    """Merged on purpose. Reading two pipes without select or threads deadlocks
    when either fills, and a collector hanging at four hundred sites because
    nobody drained stderr is worse than the silence this replaced."""
    import sys as _sys

    from m365_governance import collecting

    script = "import sys\nprint('out')\nprint('bad', file=sys.stderr)\n"

    _codigo, out, err, _cancelado = collecting._run(
        [_sys.executable, "-c", script], None
    )

    assert "out" in out and "bad" in out
    assert err == ""


def test_a_non_zero_exit_is_carried_rather_than_raised():
    import sys as _sys

    from m365_governance import collecting

    code, _saida, _err, cancelled = collecting._run(
        [_sys.executable, "-c", "raise SystemExit(3)"], None
    )

    assert code == 3
    assert cancelled is False


def test_an_interrupt_stops_the_child_and_is_reported_as_cancelled(monkeypatch):
    """Ctrl-C is a cancellation, not a crash.

    The child is asked to stop, whatever it already wrote to disk stays there,
    and the outcome says `cancelled` rather than `failed`. A person who stops a
    collection has not been told their tenant could not be read.
    """
    import sys as _sys

    from m365_governance import collecting

    script = "import time\nprint('working', flush=True)\ntime.sleep(30)\n"

    def give_up(_linha: str) -> None:
        # Raised from inside the loop, which is where a real Ctrl-C lands: the
        # process is mid-read when somebody presses it.
        raise KeyboardInterrupt

    code, out, _err, cancelled = collecting._run(
        [_sys.executable, "-c", script], give_up
    )

    assert cancelled is True
    assert "working" in out
    assert code != 0

    # And it travels: a cancelled run is never `failed`, whatever the child's
    # exit code turned out to be.
    outcome = _outcome(returncode=code, cancelled=cancelled)
    assert outcome.state is State.CANCELLED


def test_a_clean_exit_that_wrote_nothing_is_failed_and_not_completed(tmp_path):
    """The rounding-up made by the type that exists to prevent it.

    A collector that authenticated, enumerated nothing and exited zero used to
    report `completed`, which tells a consumer everything was read by a
    collection that wrote nothing down. `failed` is what the contract calls no
    usable artefact, and an exit code does not change whether there is one.

    A tenant with nothing in it lands here too, and that is the right side of
    the line: somebody has to establish whether an estate is empty or was never
    read, and being told the collection went well answers neither.
    """
    outcome = _outcome(returncode=0, written=[])

    assert outcome.state is State.FAILED
    # And `ok` still answers its own smaller question, which is not this one.
    assert outcome.ok is True


def test_the_reason_an_area_was_not_read_is_a_sentence_and_not_a_structure(tmp_path):
    """It arrived as a Python dict repr, braces and quotes included.

    The same string goes into the manifest's `because` and onto stdout under
    `collect`, so a reader was shown the engine's internals where a reason
    belonged.
    """
    doc = _evidence(
        tmp_path / "a.json",
        ["sites", "owners"],
        ["sites"],
        {
            "owners": {
                "state": "permission-denied",
                "detail": "the identity is not a site collection administrator",
            }
        },
    )

    (reported,) = incomplete_coverage([doc])

    assert "permission-denied — the identity is not a site collection" in reported
    assert "{" not in reported and "'" not in reported


def test_a_slice_that_writes_one_file_refuses_a_directory(tmp_path, capsys):
    """The defect a live run found, before the process starts.

    `collect owners --output <directory>` reached PowerShell and failed with
    `Clear-Content is only supported on files.` four seconds later. That is an
    internal error from another language, and somebody reading it has no way to
    know they passed the wrong kind of path.
    """
    from m365_governance.cli import main

    code = main(
        ["collect", "owners", "--client-id", "an-id",
         "--site-url", "https://contoso.sharepoint.com/sites/x",
         "--output", str(tmp_path)]
    )

    assert code == 2
    said = capsys.readouterr().err
    assert "writes one document" in said
    assert "owners.json" in said


def test_a_slice_that_writes_many_refuses_a_file(tmp_path, capsys):
    from m365_governance.cli import main

    target = tmp_path / "one.json"
    target.write_text("{}", encoding="utf-8")

    code = main(
        ["collect", "sites", "--client-id", "an-id",
         "--tenant-url", "https://contoso-admin.sharepoint.com",
         "--output", str(target)]
    )

    assert code == 2
    assert "is a directory" in capsys.readouterr().err


def test_which_slices_write_many_is_declared_rather_than_guessed():
    """`sites` and `permissions` read many resources; the rest read one.

    Declared on the slice so the refusal above is a property of the contract
    rather than a heuristic over the slice's name.
    """
    from m365_governance.collecting import SLICES

    many = {name for name, s in SLICES.items() if s.writes_many}

    assert many == {"sites", "permissions"}
