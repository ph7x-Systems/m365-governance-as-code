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

from conftest import DATA, FIXTURES, evidence
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
    shutil.copy(FIXTURES / "site-two-owners.json", tmp_path / "a.json")
    shutil.copy(FIXTURES / "site-two-owners.json", tmp_path / "b.json")
    code, _, err = run(capsys, "evaluate", "--evidence", str(tmp_path))
    assert code == 2
    assert "duplicate resource ids" in err
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


def test_diff_pairs_resources_by_id_and_shows_what_moved(capsys, tmp_path):
    before = _stored_set(tmp_path, "before", "site-two-owners")
    after_set = RunSet([_run_for("site-one-owner")])
    # The same resource, one owner later. Renaming the id is how a fixture
    # becomes the same site at a different moment.
    after_set.runs[0].resource["id"] = "contoso,site,finance"
    after_set.runs[0].resource["display_name"] = "Finance"
    after = tmp_path / "after.json"
    after.write_text(json.dumps(after_set.to_dict()))

    code, out, _ = run(capsys, "diff", str(before), str(after))
    assert code == 0
    assert "## Finance" in out
    assert "pass → fail" in out
    assert "`owners.count` | 2 | 1" in out


def test_diff_names_a_resource_that_appeared_and_one_that_went(capsys, tmp_path):
    before = _stored_set(tmp_path, "before", "site-two-owners")
    after = _stored_set(tmp_path, "after", "site-spfx-behind")

    code, out, _ = run(capsys, "diff", str(before), str(after))
    assert code == 0
    assert "(new resource)" in out
    assert "(resource gone)" in out
    assert "not a resource that passed" in out


def test_diff_still_separates_the_rule_moving_from_the_estate_moving():
    """The question an audit asks is whether the estate changed or we did, and
    it does not stop being the question at tenant scale."""
    before = RunSet([_run_for("site-two-owners")])
    after = RunSet([_run_for("site-two-owners")])
    after.runs[0].results[0].rule_version = "9.9"

    text = diffing.many_to_markdown(before, after)
    assert "The rule changed too" in text
    assert "may be the rule rather than the estate" in text


def test_a_quiet_diff_says_so(capsys, tmp_path):
    before = _stored_set(tmp_path, "before", "site-two-owners")
    code, out, _ = run(capsys, "diff", str(before), str(before))
    assert code == 0
    assert "Nothing changed" in out


def test_a_regression_anywhere_in_the_set_fails_the_pipeline(capsys, tmp_path):
    before = _stored_set(tmp_path, "before", "site-two-owners")
    after_set = RunSet([_run_for("site-one-owner")])
    after_set.runs[0].resource["id"] = "contoso,site,finance"
    after = tmp_path / "after.json"
    after.write_text(json.dumps(after_set.to_dict()))

    code, _, _ = run(capsys, "diff", str(before), str(after), "--fail-on-regression")
    assert code == 1


def test_a_run_and_a_run_set_are_not_comparable(capsys, tmp_path):
    """One is a resource, the other an estate. Comparing them would either
    hide every other resource or invent one."""
    run_set = _stored_set(tmp_path, "set", "site-two-owners")
    code, _, err = run(
        capsys, "diff", str(run_set), str(FIXTURES / "site-one-owner.json")
    )
    assert code == 2
    assert "cannot diff a single resource against a run set" in err


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
