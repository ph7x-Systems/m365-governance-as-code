"""The CLI and the two report formats."""

from __future__ import annotations

import json

from conftest import DATA, evidence, rule
from m365_governance.cli import main
from m365_governance.engine import evaluate
from m365_governance.reporting import to_json, to_markdown


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_validate_passes_on_the_repository(capsys):
    code, out, _ = run(capsys, "validate", "--rules", str(DATA / "rules"))
    assert code == 0
    assert "No problems found" in out


def test_evaluate_produces_markdown(capsys):
    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(DATA / "rules"),
        "--evidence",
        str(DATA / "fixtures/sharepoint/list-over-limit.json"),
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
        str(DATA / "rules"),
        "--evidence",
        str(DATA / "fixtures/sharepoint/list-over-limit.json"),
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
        str(DATA / "rules"),
        "--evidence",
        str(DATA / "fixtures/sharepoint/list-count-not-collected.json"),
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
        str(DATA / "rules"),
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
    # Read the version from the rule rather than pinning it: the assertion is
    # that the report carries it, not that it never moves.
    result = payload["results"][0]
    assert result["rule_version"] == rule("SPO-SITE-001")["version"]
    assert result["schema_version"] == rule("SPO-SITE-001")["schema_version"]


# ---------------------------------------------------------------------------
# the diff as a model, not only as prose
# ---------------------------------------------------------------------------


def _two_runs():
    from conftest import evidence, rule
    from m365_governance.engine import evaluate

    rules = [rule("SPO-SHARE-003"), rule("SPO-SHARE-004")]
    return (
        evaluate(rules, evidence("tenant-sharing-default-anyone-and-edit")),
        evaluate(rules, evidence("tenant-sharing-mitigated")),
    )


def test_the_diff_has_a_model_and_not_only_markdown():
    """Markdown used to be the only way out of `diff`, which made it the one
    surface a reader had to parse prose to consume. Anything needing to know
    what changed would have re-derived it, and a second derivation of "what
    changed" is a second answer to the question the product exists for."""
    import json

    from m365_governance import diffing

    before, after = _two_runs()
    document = json.loads(diffing.to_json(before, after))

    assert document["diff_schema_version"] == "1.0"
    assert document["counts"]["rules_differing"] == 2
    assert document["counts"]["outcome_changed"] == 2
    assert document["counts"]["regressions"] == 0
    assert [c["rule_id"] for c in document["changes"]] == [
        "SPO-SHARE-003",
        "SPO-SHARE-004",
    ]


def test_the_model_states_the_kind_rather_than_leaving_it_to_be_inferred():
    """A consumer working `added`/`removed`/`changed` out from the two
    outcomes would be making the semantic decision the engine already made,
    and two consumers would eventually disagree about it."""
    from m365_governance import diffing

    before, after = _two_runs()
    document = diffing.to_dict(before, after)
    assert {c["kind"] for c in document["changes"]} == {"changed"}
    for change in document["changes"]:
        assert change["before"]["outcome"] == "fail"
        assert change["after"]["outcome"] == "pass"


def test_both_renderings_describe_the_same_comparison():
    """Markdown is what a person reads and JSON is what everything else reads.
    They are projections of one comparison, so they cannot disagree about which
    rules moved."""
    import re

    from m365_governance import diffing

    before, after = _two_runs()
    prose = diffing.to_markdown(before, after)
    document = diffing.to_dict(before, after)

    in_prose = set(re.findall(r"SPO-[A-Z]+-\d+", prose))
    assert in_prose == {c["rule_id"] for c in document["changes"]}
    assert f"{document['counts']['rules_differing']} rules differ" in prose


def test_the_model_carries_the_whole_result_on_each_side():
    """Summarising them would be a third description of a result, and a
    consumer wanting the basis or the sources would have to go and find the
    run again."""
    from m365_governance import diffing

    before, after = _two_runs()
    change = diffing.to_dict(before, after)["changes"][0]

    assert change["before"]["basis"] == "documented-guidance"
    assert change["after"]["sources"]
    assert change["evidence"] == [
        {
            "path": "tenant_sharing.default_link_type",
            "before": "AnonymousAccess",
            "after": "Internal",
        }
    ]
