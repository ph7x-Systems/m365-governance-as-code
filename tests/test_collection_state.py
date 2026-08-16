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

    assert outcome.state is State.COMPLETED
    assert "-Mode" in outcome.stdout and "TenantSites" in outcome.stdout
    assert outcome.written == []


def test_run_slice_accepts_a_progress_callback(tmp_path):
    """The signature is the contract a caller builds against.

    A dry run reaches nothing, so this asserts the door exists rather than what
    comes through it: a test that needed a tenant to prove a callback would
    never run anywhere."""
    linhas: list[str] = []

    run_slice(
        "sites",
        client_id="00000000-0000-0000-0000-000000000000",
        output=tmp_path,
        tenant_url="https://contoso-admin.sharepoint.com",
        dry_run=True,
        on_progress=linhas.append,
    )

    assert linhas == []


def test_a_missing_collector_host_is_an_outcome_and_not_a_traceback(
    tmp_path, monkeypatch
):
    """`pwsh` absent is the ordinary case on a machine that only evaluates.

    It must arrive as a failed collection rather than as an exception, because
    a caller watching a collection cannot show a stack trace to somebody who
    just wanted to know whether their tenant was read."""
    import m365_governance.collecting as collecting

    def sem_pwsh(*args, **kwargs):
        raise FileNotFoundError("pwsh")

    monkeypatch.setattr(collecting.subprocess, "Popen", sem_pwsh)

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

    guiao = (
        "import sys, time\n"
        "print('first', flush=True)\n"
        "time.sleep(0.4)\n"
        "print('second', flush=True)\n"
    )

    momentos: list[tuple[str, float]] = []
    inicio = _time.monotonic()
    codigo, saida, _erro, cancelado = collecting._run(
        [_sys.executable, "-c", guiao],
        lambda linha: momentos.append((linha, _time.monotonic() - inicio)),
    )

    assert codigo == 0
    assert cancelado is False
    assert [linha for linha, _ in momentos] == ["first", "second"]
    assert saida == "first\nsecond"

    # The first line has to arrive before the child has finished. Buffered, both
    # would land together at the end, which is what `capture_output=True` did.
    primeiro, segundo = momentos[0][1], momentos[1][1]
    assert segundo - primeiro > 0.2, (
        f"both lines arrived together ({primeiro:.2f}s, {segundo:.2f}s): the "
        f"output is buffered and nothing can report progress"
    )


def test_stderr_is_in_the_stream_where_somebody_watching_will_see_it():
    """Merged on purpose. Reading two pipes without select or threads deadlocks
    when either fills, and a collector hanging at four hundred sites because
    nobody drained stderr is worse than the silence this replaced."""
    import sys as _sys

    from m365_governance import collecting

    guiao = "import sys\nprint('out')\nprint('bad', file=sys.stderr)\n"

    _codigo, saida, erro, _cancelado = collecting._run(
        [_sys.executable, "-c", guiao], None
    )

    assert "out" in saida and "bad" in saida
    assert erro == ""


def test_a_non_zero_exit_is_carried_rather_than_raised():
    import sys as _sys

    from m365_governance import collecting

    codigo, _saida, _erro, cancelado = collecting._run(
        [_sys.executable, "-c", "raise SystemExit(3)"], None
    )

    assert codigo == 3
    assert cancelado is False


def test_an_interrupt_stops_the_child_and_is_reported_as_cancelled(monkeypatch):
    """Ctrl-C is a cancellation, not a crash.

    The child is asked to stop, whatever it already wrote to disk stays there,
    and the outcome says `cancelled` rather than `failed`. A person who stops a
    collection has not been told their tenant could not be read.
    """
    import sys as _sys

    from m365_governance import collecting

    guiao = "import time\nprint('working', flush=True)\ntime.sleep(30)\n"

    def desiste(_linha: str) -> None:
        # Raised from inside the loop, which is where a real Ctrl-C lands: the
        # process is mid-read when somebody presses it.
        raise KeyboardInterrupt

    codigo, saida, _erro, cancelado = collecting._run(
        [_sys.executable, "-c", guiao], desiste
    )

    assert cancelado is True
    assert "working" in saida
    assert codigo != 0

    # And it travels: a cancelled run is never `failed`, whatever the child's
    # exit code turned out to be.
    outcome = _outcome(returncode=codigo, cancelled=cancelado)
    assert outcome.state is State.CANCELLED
