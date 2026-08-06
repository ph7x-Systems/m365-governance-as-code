"""The CLI and the two report formats."""

from __future__ import annotations

import json

from conftest import ROOT, evidence, rule
from m365_governance.cli import main
from m365_governance.engine import evaluate
from m365_governance.reporting import to_json, to_markdown


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_validate_passes_on_the_repository(capsys):
    code, out, _ = run(capsys, "validate", "--rules", str(ROOT / "rules"))
    assert code == 0
    assert "No problems found" in out


def test_evaluate_produces_markdown(capsys):
    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(ROOT / "rules"),
        "--evidence",
        str(ROOT / "fixtures/sharepoint/list-over-limit.json"),
        "--format",
        "markdown",
    )
    assert code == 0
    assert "# Governance report" in out
    assert "documented-limit" in out


def test_evaluate_produces_json(capsys):
    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(ROOT / "rules"),
        "--evidence",
        str(ROOT / "fixtures/sharepoint/list-over-limit.json"),
        "--format",
        "json",
    )
    assert code == 0
    payload = json.loads(out)
    assert payload["counts"]["fail"] == 1
    assert payload["results"][0]["basis"] == "documented-limit"
    assert payload["results"][0]["rule_version"] == "2.0"


def test_fail_on_unresolved_counts_unknown_as_unresolved(capsys):
    code, _, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(ROOT / "rules"),
        "--evidence",
        str(ROOT / "fixtures/sharepoint/list-count-not-collected.json"),
        "--fail-on",
        "unresolved",
    )
    assert code == 1


def test_evaluate_refuses_malformed_evidence(capsys, tmp_path):
    bad = tmp_path / "evidence.json"
    bad.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    code, _, err = run(
        capsys,
        "evaluate",
        "--rules",
        str(ROOT / "rules"),
        "--evidence",
        str(bad),
    )
    assert code == 2
    assert "defect in the collector" in err


# ---------------------------------------------------------------------------
# What a report may not do
# ---------------------------------------------------------------------------


def _run_one(fixture: str):
    return evaluate([rule("SPO-SITE-001"), rule("SPO-LIST-001")], evidence(fixture))


def test_unknown_is_never_counted_as_a_pass():
    run_result = _run_one("site-owners-not-collected")
    counts = run_result.counts()
    assert counts["pass"] == 0
    assert counts["unknown"] == 1
    assert "not compliance" in to_markdown(run_result)


def test_not_applicable_is_not_counted_as_an_answer():
    markdown = to_markdown(_run_one("list-unique-permissions"))
    assert "**0 produced an answer.**" in markdown


def test_a_delegated_run_says_so():
    markdown = to_markdown(_run_one("site-delegated-identity"))
    assert "Identity: delegated" in markdown
    assert "one person sees" in markdown


def test_a_pass_carries_what_it_does_not_establish():
    markdown = to_markdown(_run_one("site-two-owners"))
    assert "This pass does not establish" in markdown
    assert "dormant" in markdown


def test_uncollected_blocks_are_disclosed():
    markdown = to_markdown(_run_one("site-owners-not-collected"))
    assert "Not collected" in markdown
    assert "permission-denied" in markdown


def test_json_report_carries_rule_and_schema_versions():
    payload = json.loads(to_json(_run_one("site-two-owners")))
    result = payload["results"][0]
    assert result["rule_version"] == "1.0"
    assert result["schema_version"] == "1.0"
