"""The CLI and the two report formats."""

from __future__ import annotations

import json

from conftest import DATA, evidence, rule
from m365_governance import registry
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

    assert document["$schema"] == registry.contract("comparison")
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


def test_the_diff_resource_has_the_same_shape_as_every_other():
    """Found by the desktop surface refusing to parse it. A resource reference
    without a type is not one, and emitting a narrower shape here would make
    the diff the only document a consumer has to special-case."""
    from m365_governance import diffing

    before, after = _two_runs()
    resource = diffing.to_dict(before, after)["resource"]
    # The structured reference, not a bare id. Identity is three fields now,
    # and a consumer compares them rather than agreeing on a string.
    assert set(resource) >= {"workload", "type", "native_id"}
    assert resource["type"] == "tenant"


def test_a_result_carries_the_rules_own_name():
    """An id identifies; a title says what was checked. A report that carries
    only the message loses the name of the thing that produced it, which is
    what a person cites in a sentence."""
    from conftest import evidence, rule
    from m365_governance.engine import evaluate_rule

    result = evaluate_rule(rule("SPO-SHARE-003"), evidence("tenant-sharing-mitigated"))
    assert result.title == "The organisation default sharing link should not be Anyone"
    assert result.to_dict()["title"] == result.title


# ── the migration commands ───────────────────────────────────────────────────
#
# `migration-verify` was the largest untested block in this module: sixty-eight
# lines that load two reads, refuse the ones that cannot support a record, and
# decide the exit code. The exit code is the part that matters most, because it
# is what a pipeline acts on — and the rule it encodes is the one this whole
# contract exists for: `unknown` is not a failure. An operator who could not
# read half the estate has a coverage problem, not a migration problem.


def _read(tmp_path, name, *, taken_at, items, coverage=None):
    """A migration read on disk, as the command expects to find one."""
    from m365_governance import migration

    document = {
        "$schema": migration.read_contract(),
        "read_id": name,
        "taken_at": taken_at,
        "estate": "contoso-projects",
        "produced_by": "m365-governance 0.1.0",
        "coverage": coverage or [],
        "items": items,
        "read_by": {
            "kind": "delegated",
            "principal": "an operator",
            "scopes": ["Files.Read.All"],
        },
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


PLAN = "/Shared Documents/plan.xlsx"


def test_migration_verify_reports_nothing_when_the_move_carried_everything(
    capsys, tmp_path
):
    before = _read(
        tmp_path,
        "baseline",
        taken_at="2026-03-01T09:00:00Z",
        items={PLAN: {"size": 12}},
    )
    after = _read(
        tmp_path,
        "verification",
        taken_at="2026-03-08T09:00:00Z",
        items={PLAN: {"size": 12}},
    )
    code, out, _ = run(
        capsys,
        "migration-verify",
        str(before),
        str(after),
        "--kind",
        "tenant-to-tenant",
    )
    # ZERO, and `unknown` is why this test exists. Both sides carry a size and
    # nothing else, so content was never established: the record says `unknown`
    # rather than `pass`, and the exit code is still zero. A size that matches
    # does not prove a file that matches, and an unknown is not a failed
    # migration; it is a thin read.
    assert code == 0
    assert "contoso-projects" in out
    assert "unknown" in out
    assert "fail" not in out
    assert "digest" in out


def test_migration_verify_exits_one_when_something_did_not_arrive(capsys, tmp_path):
    before = _read(
        tmp_path,
        "baseline",
        taken_at="2026-03-01T09:00:00Z",
        items={PLAN: {"size": 12}},
    )
    after = _read(tmp_path, "verification", taken_at="2026-03-08T09:00:00Z", items={})
    code, out, _ = run(
        capsys,
        "migration-verify",
        str(before),
        str(after),
        "--kind",
        "tenant-to-tenant",
    )
    assert code == 1
    assert "fail" in out


def test_migration_verify_refuses_a_document_that_is_not_a_read(capsys, tmp_path):
    """A wrong file is refused by CONTRACT, not by guessing at its shape."""
    stranger = tmp_path / "strange.json"
    stranger.write_text(
        json.dumps({"$schema": "https://example.test/other"}), encoding="utf-8"
    )
    other = _read(tmp_path, "verification", taken_at="2026-03-08T09:00:00Z", items={})
    code, _, err = run(
        capsys, "migration-verify", str(stranger), str(other), "--kind", "t"
    )
    assert code == 2
    assert "not a migration read" in err


def test_migration_verify_refuses_a_baseline_that_is_not_earlier(capsys, tmp_path):
    """The refusal is the product. A record built from a baseline taken after
    the verification would travel as evidence of a move it cannot describe."""
    before = _read(tmp_path, "baseline", taken_at="2026-03-08T09:00:00Z", items={})
    after = _read(tmp_path, "verification", taken_at="2026-03-01T09:00:00Z", items={})
    code, _, err = run(
        capsys, "migration-verify", str(before), str(after), "--kind", "t"
    )
    assert code == 1
    assert err.strip()


def test_migration_verify_writes_the_record_and_a_report(capsys, tmp_path):
    before = _read(
        tmp_path,
        "baseline",
        taken_at="2026-03-01T09:00:00Z",
        items={PLAN: {"size": 12}},
    )
    after = _read(
        tmp_path,
        "verification",
        taken_at="2026-03-08T09:00:00Z",
        items={PLAN: {"size": 12}},
    )
    record_path = tmp_path / "out" / "record.json"
    report_path = tmp_path / "out" / "report.html"
    code, _, _ = run(
        capsys,
        "migration-verify",
        str(before),
        str(after),
        "--kind",
        "tenant-to-tenant",
        "--performed-by",
        "a migration tool",
        "--out",
        str(record_path),
        "--report",
        str(report_path),
    )
    assert code == 0
    written = json.loads(record_path.read_text())
    assert written["move"]["performed_by"] == "a migration tool"
    # The extension chooses the format: an `.html` that came out as Markdown
    # would be a file that opens in a browser and shows its own source.
    assert report_path.read_text().lstrip().startswith("<")


def test_migration_verify_says_what_could_not_be_read(capsys, tmp_path):
    """A gap is not a failure, and the exit code says so: the operator has a
    coverage problem, and conflating the two is what this contract refuses."""
    gap = [{"scope": "/Shared Documents/Archive", "state": "permission-denied"}]
    before = _read(
        tmp_path,
        "baseline",
        taken_at="2026-03-01T09:00:00Z",
        items={PLAN: {"size": 12}},
        coverage=gap,
    )
    after = _read(
        tmp_path,
        "verification",
        taken_at="2026-03-08T09:00:00Z",
        items={PLAN: {"size": 12}},
    )
    code, out, _ = run(
        capsys, "migration-verify", str(before), str(after), "--kind", "t"
    )
    assert code == 0
    assert "not read" in out
    assert "permission-denied" in out
