"""The loop, closed: collect → evaluate → save run → report → diff.

The property under test is that the envelope `evaluate` writes is the one
`report` and `diff` read. Until that held, reproducibility was a design goal
rather than a property: `evaluate` emitted a shape its own sibling commands
rejected, and a tenant-scale run could be produced but never reopened.

Everything here is about the many-resource shape. The single-resource one is
covered in test_commands.py and is deliberately left alone.
"""

from __future__ import annotations

import json
import shutil

import pytest

from conftest import DATA, FIXTURES, ROOT, evidence
from m365_governance import diffing
from m365_governance.cli import main
from m365_governance.engine import evaluate
from m365_governance.loader import load_rules
from m365_governance.reporting import many_to_html, many_to_json, many_to_markdown
from m365_governance.results import DuplicateResource, Outcome, RunSet

RULES = DATA / "rules"


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _run_for(fixture: str):
    return evaluate([loaded.data for loaded in load_rules(RULES)], evidence(fixture))


def _directory(path, *fixtures):
    """A directory of evidence, which is what a tenant collection produces."""
    path.mkdir(parents=True, exist_ok=True)
    for name in fixtures:
        shutil.copy(FIXTURES / f"{name}.json", path / f"{name}.json")
    return path


# ---------------------------------------------------------------------------
# the envelope
# ---------------------------------------------------------------------------


def test_a_directory_of_one_has_the_shape_of_a_directory_of_many(capsys, tmp_path):
    """The shape follows what was asked for, not how many files were there.

    A directory holding one document today and fifty next quarter must not
    change what a pipeline parses, or every consumer grows a branch for the
    day somebody deleted a site.
    """
    one = _directory(tmp_path / "one", "site-two-owners")
    many = _directory(tmp_path / "many", "site-two-owners", "site-spfx-behind")

    shapes = []
    for path in (one, many):
        _, out, _ = run(capsys, "evaluate", "--evidence", str(path), "--format", "json")
        shapes.append(set(json.loads(out)))
    assert shapes[0] == shapes[1]
    assert "runs" in shapes[0] and "run_coverage" in shapes[0]


def test_a_single_file_is_still_a_single_run(capsys):
    """The other half of the same promise: a file is one resource, not a set
    of one. A caller who asked about one site gets an answer about one site."""
    _, out, _ = run(
        capsys,
        "evaluate",
        "--evidence",
        str(FIXTURES / "site-two-owners.json"),
        "--format",
        "json",
    )
    payload = json.loads(out)
    assert "results" in payload
    assert "runs" not in payload


def test_the_envelope_survives_the_round_trip():
    """A field lost here disappears the second time somebody opens the run."""
    runs = [_run_for("site-two-owners"), _run_for("site-spfx-behind")]
    original = RunSet(runs).to_dict()
    assert RunSet.from_dict(original).to_dict() == original


def test_counts_are_the_sum_of_the_runs():
    runs = [_run_for("site-two-owners"), _run_for("site-spfx-behind")]
    total = RunSet(runs).counts()
    for outcome in Outcome:
        assert total[outcome.value] == sum(r.counts()[outcome.value] for r in runs), (
            f"{outcome.value} does not add up"
        )


# ---------------------------------------------------------------------------
# coverage: absence is never completeness
# ---------------------------------------------------------------------------


def test_absent_coverage_is_not_established_rather_than_complete():
    """Counting the documents that exist proves how many resources were
    observed. It cannot prove how many the identity failed to return, and a
    run that reported 47 without saying "of 53" is the inconsistency the run
    level exists to remove."""
    coverage = RunSet([_run_for("site-two-owners")]).run_coverage()
    assert coverage["state"] == "not-established"
    assert coverage["expected"] is None
    assert coverage["observed"] == 1
    assert "does not establish complete coverage" in coverage["detail"]


def test_a_recorded_expectation_is_reported_as_one():
    run_set = RunSet(
        [_run_for("site-two-owners")],
        coverage={"state": "partial", "observed": 47, "expected": 53},
    )
    assert "47 of 53" in many_to_markdown(run_set)


@pytest.mark.parametrize("render", [many_to_markdown, many_to_html])
def test_every_format_says_coverage_was_not_established(render):
    assert "not established" in render(RunSet([_run_for("site-two-owners")]))


# ---------------------------------------------------------------------------
# two documents about one resource
# ---------------------------------------------------------------------------


def test_duplicate_resource_ids_are_refused():
    """The engine will not average two answers about one resource. A run set
    that counted a site twice would report a number no tenant has."""
    runs = [_run_for("site-two-owners"), _run_for("site-two-owners")]
    with pytest.raises(DuplicateResource) as caught:
        RunSet(runs)
    assert "contoso,site,finance" in str(caught.value)


def test_the_command_line_says_which_resource_rather_than_a_traceback(capsys, tmp_path):
    """The same evidence twice is still refused, and it says which resource.

    Documents about ONE resource are now composed, because that is what
    collecting several slices of a site produces and the pipeline has to carry
    it. What is not composed is the same fact block arriving twice: identical
    or not, one of them would be dropped, and nobody here can promise the
    caller meant that.
    """
    shutil.copy(FIXTURES / "site-two-owners.json", tmp_path / "a.json")
    shutil.copy(FIXTURES / "site-two-owners.json", tmp_path / "b.json")
    code, _, err = run(capsys, "evaluate", "--evidence", str(tmp_path))
    assert code == 2
    assert "`owners`" in err
    assert "contoso,site,finance" in err
    assert "Traceback" not in err


# ---------------------------------------------------------------------------
# the three formats agree
# ---------------------------------------------------------------------------


def test_the_formats_report_the_same_counts():
    """A report that said one thing on paper and another in the browser would
    be two reports."""
    run_set = RunSet([_run_for("site-two-owners"), _run_for("site-spfx-behind")])
    counts = json.loads(many_to_json(run_set))["counts"]
    markdown, html = many_to_markdown(run_set), many_to_html(run_set)

    for outcome, label in (
        (Outcome.FAIL, "Fail"),
        (Outcome.UNKNOWN, "Unknown"),
        (Outcome.PASS, "Pass"),
    ):
        n = counts[outcome.value]
        assert f"| {label} | {n} |" in markdown
        assert f"<td>{label}</td><td>{n}</td>" in html


def test_the_many_resource_html_is_self_contained():
    html = many_to_html(RunSet([_run_for("site-two-owners")]))
    assert "<script" not in html
    assert "@import" not in html
    assert 'rel="stylesheet"' not in html
    assert 'src="http' not in html


def test_asking_for_html_over_a_directory_returns_html(capsys, tmp_path):
    """It returned Markdown, silently, because there was no many-resource HTML
    to return. A format flag that is accepted and ignored is worse than one
    that is refused."""
    _directory(tmp_path, "site-two-owners", "site-spfx-behind")
    _, out, _ = run(capsys, "evaluate", "--evidence", str(tmp_path), "--format", "html")
    assert out.startswith("<!doctype html>")
    assert "Governance report" in out


def test_the_delegated_warning_survives_the_many_resource_report(tmp_path):
    run_set = RunSet([_run_for("site-delegated-identity")])
    for rendered in (many_to_markdown(run_set), many_to_html(run_set)):
        assert "Identity: delegated" in rendered


# ---------------------------------------------------------------------------
# report re-reads what evaluate wrote
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["markdown", "json", "html"])
def test_report_reopens_a_stored_run_set(capsys, tmp_path, fmt):
    """The loop, in one test: evaluate a directory, keep the file, reopen it."""
    source = _directory(tmp_path / "evidence", "site-two-owners", "site-spfx-behind")
    _, out, _ = run(capsys, "evaluate", "--evidence", str(source), "--format", "json")

    stored = tmp_path / "run.json"
    stored.write_text(out)

    code, rendered, _ = run(capsys, "report", str(stored), "--format", fmt)
    assert code == 0
    assert rendered.strip()
    assert "Portal" in rendered or "Finance" in rendered


def test_report_of_a_stored_run_set_matches_what_evaluate_printed(capsys, tmp_path):
    """Re-rendering is not re-evaluating. The bytes must be the same."""
    source = _directory(tmp_path / "evidence", "site-two-owners", "site-spfx-behind")
    _, evaluated, _ = run(
        capsys, "evaluate", "--evidence", str(source), "--format", "json"
    )
    stored = tmp_path / "run.json"
    stored.write_text(evaluated)

    _, reported, _ = run(capsys, "report", str(stored), "--format", "json")
    assert json.loads(reported) == json.loads(evaluated)


def test_report_still_refuses_an_evidence_document(capsys):
    code, _, err = run(capsys, "report", str(FIXTURES / "site-one-owner.json"))
    assert code == 2
    assert "not a report" in err


# ---------------------------------------------------------------------------
# diff, at tenant scale
# ---------------------------------------------------------------------------


def _stored_set(tmp_path, name, *fixtures):
    runs = [_run_for(f) for f in fixtures]
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(RunSet(runs).to_dict()))
    return path


def test_the_run_level_comparison_pairs_by_id_and_shows_what_moved():
    """Driven directly rather than through a command, because it is not one.

    A comparison is a relation between two assessments and this is how one is
    computed underneath. It claims no contract, nothing persists it, and no
    command emits it: the day it had a public shape was the day two documents
    described the same idea and only one of them had a schema.
    """
    before = RunSet([_run_for("site-two-owners")])
    after = RunSet([_run_for("site-one-owner")])
    # The same resource, one owner later. Identity is structured now, so the
    # native id is the field that makes two documents the same site — and the
    # display name is deliberately NOT part of it, which is why setting it here
    # changes what is printed and nothing about what is paired.
    after.runs[0].resource["native_id"] = before.runs[0].resource["native_id"]
    after.runs[0].resource["display_name"] = "Finance"

    text = diffing.many_to_markdown(before, after)
    assert "## Finance" in text
    assert "pass → fail" in text
    assert "`owners.count` | 2 | 1" in text


def test_the_run_level_comparison_names_what_appeared_and_what_went():
    before = RunSet([_run_for("site-two-owners")])
    after = RunSet([_run_for("site-spfx-behind")])

    text = diffing.many_to_markdown(before, after)
    assert "(new resource)" in text
    assert "(resource gone)" in text
    assert "not a resource that passed" in text


def test_the_run_level_comparison_separates_the_rule_moving_from_the_estate():
    """The question an audit asks is whether the estate changed or we did, and
    it does not stop being the question at tenant scale."""
    before = RunSet([_run_for("site-two-owners")])
    after = RunSet([_run_for("site-two-owners")])
    after.runs[0].results[0].rule_version = "9.9"

    text = diffing.many_to_markdown(before, after)
    assert "The rule changed too" in text
    assert "may be the rule rather than the estate" in text


def test_the_run_level_comparison_is_reached_by_no_command():
    """The property that keeps it an implementation detail. If a command grew
    a way to emit this, it would be a second document describing what a
    Comparison already describes, and only one of the two would have a
    contract."""
    from m365_governance import cli

    source = (ROOT / "src" / "m365_governance" / "cli.py").read_text(encoding="utf-8")
    assert "diffing." not in source, "a command reaches the run-level comparison"
    assert "comparison.build" in source
    assert "diff" in cli._COMMANDS


# ---------------------------------------------------------------------------
# collect spfx
# ---------------------------------------------------------------------------


def test_spfx_is_reachable_from_the_command_line(capsys, tmp_path):
    """A rule and a profile existed that no command could feed. A capability
    only its author can reach is not a capability."""
    code, out, _ = run(
        capsys,
        "collect",
        "spfx",
        "--client-id",
        "00000000-0000-0000-0000-000000000000",
        "--site-url",
        "https://contoso.sharepoint.com",
        "--output",
        str(tmp_path / "spfx.json"),
        "--dry-run",
    )
    assert code == 0
    assert "-Mode SpfxCatalog" in out
    assert not (tmp_path / "spfx.json").exists()


def test_spfx_collects_what_its_profile_can_answer():
    """The pairing is the point. `sites` against the ownership profile once
    produced 106 `unknown` results across 53 real sites."""
    import yaml

    from m365_governance import collecting

    chosen = collecting.SLICES["spfx"]
    profile = yaml.safe_load((DATA / "profiles" / f"{chosen.profile}.yaml").read_text())
    on_disk = {loaded.data["id"]: loaded.data for loaded in load_rules(RULES)}
    selected = [on_disk[r] for r in profile["rules"]]

    outcomes = [
        result.outcome
        for result in evaluate(selected, evidence(chosen.shaped_like)).results
    ]
    assert outcomes
    assert any(o is not Outcome.UNKNOWN for o in outcomes)
