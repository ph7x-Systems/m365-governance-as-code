"""The commands that read, and the two that re-read a conclusion.

None of these reaches a new conclusion, and that is the property worth
testing: `list-rules`, `show-rule`, `doctor` and `stats` never evaluate, and
`report` and `diff` never re-evaluate what was already decided.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import DATA, FIXTURES, ROOT, evidence
from m365_governance import doctor, inspect, registry
from m365_governance.cli import main
from m365_governance.engine import evaluate
from m365_governance.reporting import to_html, to_markdown
from m365_governance.results import Outcome, Run

RULES = DATA / "rules"


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _run_for(fixture: str) -> Run:
    """Every rule on disk, not a hand-picked pair. The pair went stale the
    first time a rule was added, which is the same way the default profile
    went stale."""
    from m365_governance.loader import load_rules

    return evaluate([loaded.data for loaded in load_rules(RULES)], evidence(fixture))


# ---------------------------------------------------------------------------
# list-rules
# ---------------------------------------------------------------------------


def test_list_rules_names_the_kind_of_claim(capsys):
    code, out, _ = run(capsys, "list-rules", "--rules", str(RULES))
    assert code == 0
    assert "SPO-LIST-001" in out and "SPO-SITE-001" in out
    assert "documented-limit" in out and "convention" in out
    # Derived, not pinned. This assertion was a literal count and broke every
    # time a rule was added, which taught nobody anything each time.
    from m365_governance.loader import load_rules

    assert f"{len(load_rules(RULES))} rules" in out


def test_list_rules_orders_the_strongest_claim_first(capsys):
    """A reader scanning the list meets `requirement` before `opinion`."""
    _, out, _ = run(capsys, "list-rules", "--rules", str(RULES))
    body = out.splitlines()
    limit = next(i for i, line in enumerate(body) if "documented-limit" in line)
    convention = next(i for i, line in enumerate(body) if "convention" in line)
    assert limit < convention


# ---------------------------------------------------------------------------
# show-rule
# ---------------------------------------------------------------------------


def test_show_rule_prints_what_it_does_not_establish(capsys):
    code, out, _ = run(capsys, "show-rule", "SPO-SITE-001", "--rules", str(RULES))
    assert code == 0
    assert "THIS RULE CAN PASS WHILE THE PROBLEM SURVIVES" in out
    assert "dormant" in out


@pytest.mark.parametrize(
    "fragment",
    ["BASIS", "SEVERITY", "EVIDENCE", "CONDITION", "OUTCOMES", "SOURCES"],
)
def test_show_rule_covers_every_section(capsys, fragment):
    _, out, _ = run(capsys, "show-rule", "SPO-LIST-001", "--rules", str(RULES))
    assert fragment in out


def test_show_rule_states_the_limit_beside_the_rule(capsys):
    _, out, _ = run(capsys, "show-rule", "SPO-LIST-001", "--rules", str(RULES))
    assert "limit: 100,000 items" in out


def test_show_rule_renders_yaml_booleans_not_python_ones(capsys):
    _, out, _ = run(capsys, "show-rule", "SPO-LIST-001", "--rules", str(RULES))
    assert "equals false" in out
    assert "False" not in out


def test_show_rule_says_which_ids_exist_when_asked_for_one_that_does_not(capsys):
    code, _, err = run(capsys, "show-rule", "SPO-NOPE-999", "--rules", str(RULES))
    assert code == 2
    assert "SPO-SITE-001" in err


def test_show_rule_says_when_no_source_is_required(capsys):
    """A convention with `sources: []` is not a rule missing its evidence."""
    _, out, _ = run(capsys, "show-rule", "SPO-SITE-001", "--rules", str(RULES))
    assert "none is required for this basis" in out


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor_is_healthy_against_the_packaged_content(capsys):
    """No `--root`, on purpose. `doctor` describes the installation, which is
    what somebody running it is asking about; pointing it at a checkout was
    how the product came to depend on one."""
    code, out, _ = run(capsys, "doctor")
    assert code == 0
    assert "Nothing is broken." in out


def test_doctor_reports_what_it_found_and_not_only_that_it_liked_it(capsys):
    _, out, _ = run(capsys, "doctor")
    import platform

    assert platform.python_version() in out
    assert "rule.schema.json" in out


def test_doctor_fails_when_a_rule_is_broken(tmp_path):
    """A rule that does not validate is a broken installation, not a warning."""
    import shutil

    shutil.copytree(DATA / "schemas", tmp_path / "schemas")
    shutil.copytree(DATA / "profiles", tmp_path / "profiles")
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "BAD-RULE-001.yaml").write_text("id: nonsense\n")

    groups, healthy = doctor.run(tmp_path)
    assert not healthy
    rules_check = next(c for _t, checks in groups for c in checks if c.name == "rules")
    assert not rules_check.ok


def test_a_missing_collector_is_not_a_failure(tmp_path):
    """PowerShell is optional. The engine and the rules never need it."""
    checks = doctor._powershell()
    assert all(not c.required for c in checks if not c.ok)


def test_doctor_catches_a_profile_selecting_a_rule_that_does_not_exist(tmp_path):
    import shutil

    shutil.copytree(DATA / "rules", tmp_path / "rules")
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "default.yaml").write_text(
        "name: default\nrules:\n  - SPO-GHOST-404\n"
    )
    checks = doctor._profiles(tmp_path)
    assert any(not c.ok for c in checks)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_stats_shows_a_bound_as_a_bound(capsys):
    code, out, _ = run(
        capsys, "stats", str(FIXTURES / "site-partial-expansion-decides.json")
    )
    assert code == 0
    assert "at least        3" in out
    assert "complete        no" in out
    assert "can never prove a fail" in out


def test_stats_warns_that_a_delegated_run_sees_one_person(capsys):
    _, out, _ = run(capsys, "stats", str(FIXTURES / "site-delegated-identity.json"))
    assert "delegated" in out
    assert "one person sees" in out


def test_stats_names_what_was_not_collected(capsys):
    _, out, _ = run(capsys, "stats", str(FIXTURES / "site-owners-not-collected.json"))
    assert "not collected" in out
    assert "permission-denied" in out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def test_report_re_renders_without_evaluating(capsys, tmp_path):
    stored = tmp_path / "run.json"
    stored.write_text(json.dumps(_run_for("list-over-limit").to_dict()))

    code, out, _ = run(capsys, "report", str(stored), "--format", "markdown")
    assert code == 0
    assert "SPO-LIST-001 v2.0" in out
    assert "documented-limit" in out


def test_report_refuses_an_evidence_document(capsys):
    code, _, err = run(capsys, "report", str(FIXTURES / "site-one-owner.json"))
    assert code == 2
    assert "not a report" in err


def test_a_stored_report_survives_the_round_trip():
    """A field lost here is a field that disappears the second time somebody
    opens the report, which is worse than never storing it."""
    original = _run_for("list-over-limit").to_dict()
    assert Run.from_dict(original).to_dict() == original


# ---------------------------------------------------------------------------
# html
# ---------------------------------------------------------------------------


def test_html_is_self_contained():
    html = to_html(_run_for("list-over-limit"))
    assert "<script" not in html
    assert "@import" not in html
    assert 'rel="stylesheet"' not in html
    # The only external URLs are the sources a rule cites, which are links a
    # reader follows, never something the page fetches.
    assert 'src="http' not in html


def test_html_spells_out_every_outcome_in_words():
    """Colour is decoration. A reader who cannot see it gets the same report."""
    for fixture, label in [
        ("list-over-limit", "Fail"),
        ("list-within-limit", "Pass"),
        ("site-owners-not-collected", "Unknown"),
        ("list-unique-permissions", "Not applicable"),
        ("list-count-invalid", "Invalid evidence"),
    ]:
        html = to_html(_run_for(fixture))
        assert f">{label}<" in html or f"{label}</" in html


def test_html_keeps_what_a_pass_does_not_establish_visible():
    html = to_html(_run_for("list-within-limit"))
    assert "This pass does not establish" in html
    assert "<details" not in html


def test_html_carries_the_delegated_warning_at_the_top():
    html = to_html(_run_for("site-delegated-identity"))
    warning = html.index("Identity: delegated")
    first_card = html.index('class="card')
    assert warning < first_card


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def assessment_of(tmp_path, name, when) -> Path:
    """One assessment of one fixture, written where the CLI can read it."""
    folder = tmp_path / name
    folder.mkdir(parents=True)
    (folder / f"{name}.json").write_text(
        (FIXTURES / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    out = tmp_path / f"{name}-assessment.json"
    code = main(
        [
            "assess",
            "--evidence",
            str(folder),
            "--created-at",
            when,
            "--out",
            str(out),
        ]
    )
    assert code == 0
    return out


def sharing_pair(tmp_path) -> tuple[Path, Path]:
    """The same tenant before and after somebody turned Anyone links off."""
    return (
        assessment_of(
            tmp_path, "tenant-sharing-default-anyone-and-edit", "2026-07-01T09:00:00Z"
        ),
        assessment_of(tmp_path, "tenant-sharing-mitigated", "2026-08-01T09:00:00Z"),
    )


def test_diff_compares_two_assessments_and_names_neither_by_path(capsys, tmp_path):
    """A comparison relates two states and belongs to neither, so it names each
    side by identity and digest. A path says where a file sat on one machine,
    not what it held."""
    before, after = sharing_pair(tmp_path)
    code, out, err = run(capsys, "diff", str(before), str(after), "--format", "json")
    assert code == 0, err

    document = json.loads(out)
    # From the registry: a literal version here is a second
    # representation that goes stale in silence.
    assert document["$schema"] == registry.contract("comparison")
    assert len(document["before"]["canonical_hash"]) == 64
    assert document["before"]["assessment_id"] != document["after"]["assessment_id"]
    # Named, never embedded: a comparison carrying both would duplicate the
    # canonical truth it describes, and the copy is what somebody edits.
    assert "canonical" not in document["before"]
    assert "runs" not in json.dumps(document["before"])


def test_diff_records_what_was_observed_and_never_why(capsys, tmp_path):
    before, after = sharing_pair(tmp_path)
    _, out, _ = run(capsys, "diff", str(before), str(after), "--format", "json")

    changes = json.loads(out)["diff"]["changes"]
    assert changes, "two different assessments produced no changes"
    for change in changes:
        assert change["kind"] in ("added", "removed", "changed")
        if change["kind"] != "changed":
            continue
        assert set(change["changes"]) <= {"evidence", "outcome", "rule-version"}
        # Nothing here evaluates causality, so nothing here may claim it.
        assert change["attribution"]["state"] in ("ambiguous", "not-evaluated")
        assert change["attribution"]["state"] != "established"


def test_the_same_assessment_twice_is_an_empty_comparison(capsys, tmp_path):
    """A legitimate question with an empty answer. Producing it proves the
    comparison is derived rather than assembled from expectations."""
    before, _ = sharing_pair(tmp_path)
    _, out, _ = run(capsys, "diff", str(before), str(before), "--format", "json")
    assert json.loads(out)["diff"]["changes"] == []


def test_a_comparison_is_reproducible(capsys, tmp_path):
    """Given the same two assessments it produces the same bytes. Nothing is
    read from the clock and nothing from the installation."""
    before, after = sharing_pair(tmp_path)
    _, first, _ = run(capsys, "diff", str(before), str(after), "--format", "json")
    _, second, _ = run(capsys, "diff", str(before), str(after), "--format", "json")
    assert first == second


def test_diff_refuses_two_tenants(capsys, tmp_path):
    """A comparison relates two states of one estate. Across two, every count
    in it would be a sum over organisations nobody manages together.

    Built rather than forged: editing the manifest would break its digest, and
    the refusal would arrive for that earlier reason instead.
    """
    before, _ = sharing_pair(tmp_path)

    folder = tmp_path / "elsewhere"
    folder.mkdir()
    document = json.loads(
        (FIXTURES / "tenant-sharing-mitigated.json").read_text(encoding="utf-8")
    )
    document["provenance"]["tenant"]["host"] = "fabrikam.sharepoint.com"
    (folder / "evidence.json").write_text(json.dumps(document), encoding="utf-8")

    after = tmp_path / "fabrikam.json"
    assert (
        main(
            [
                "assess",
                "--evidence",
                str(folder),
                "--created-at",
                "2026-08-01T09:00:00Z",
                "--out",
                str(after),
            ]
        )
        == 0
    )

    code, _, err = run(capsys, "diff", str(before), str(after))
    assert code == 2
    assert "different tenants" in err


def test_diff_refuses_an_assessment_that_does_not_verify(capsys, tmp_path):
    before, after = sharing_pair(tmp_path)
    document = json.loads(after.read_text())
    document["canonical"]["versions"]["engine"] = "forged"
    after.write_text(json.dumps(document), encoding="utf-8")

    code, _, err = run(capsys, "diff", str(before), str(after))
    assert code == 2
    assert "does not verify" in err


def test_diff_refuses_a_stored_run(capsys, tmp_path):
    """It compares assessments. A run is an evaluation; an assessment is the
    thing somebody archived, and only that can be named by an identity that
    verifies."""
    stored = tmp_path / "run.json"
    stored.write_text(
        json.dumps(_run_for("site-one-owner").to_dict()), encoding="utf-8"
    )

    code, _, err = run(capsys, "diff", str(stored), str(stored))
    assert code == 2
    assert "not an assessment" in err


def test_a_regression_fails_a_pipeline(capsys, tmp_path):
    """Leaving `pass` is the definition, and the engine's own outcomes decide
    it: nothing re-reads evidence to form a second opinion."""
    before, after = sharing_pair(tmp_path)

    # Mitigated to permissive is the direction that matters.
    code, _, _ = run(capsys, "diff", str(after), str(before), "--fail-on-regression")
    assert code == 1

    code, _, _ = run(capsys, "diff", str(before), str(after), "--fail-on-regression")
    assert code == 0


def test_the_markdown_says_what_it_does_not_say(capsys, tmp_path):
    before, after = sharing_pair(tmp_path)
    _, out, _ = run(capsys, "diff", str(before), str(after))
    assert "What changed" in out
    assert "why is not established" in out
    assert "re-evaluated" in out


# ---------------------------------------------------------------------------
# the property all six share
# ---------------------------------------------------------------------------


def test_the_reading_commands_never_reach_a_conclusion(capsys):
    """list-rules, show-rule, doctor and stats print no outcome word.

    They exist to be run before anybody trusts a result. A conclusion leaking
    into one of them would be a conclusion nobody asked for, reached without
    evidence in front of it.
    """
    verdicts = {Outcome.PASS.value, Outcome.FAIL.value}
    for argv in (
        ["list-rules", "--rules", str(RULES)],
        ["doctor"],
        ["stats", str(FIXTURES / "site-two-owners.json")],
    ):
        _, out, _ = run(capsys, *argv)
        words = set(out.lower().replace(":", " ").split())
        assert not (verdicts & words), f"{argv[0]} printed a verdict: {out}"


def test_inspect_and_doctor_import_no_engine():
    """A reading command that imported the engine would be one refactor away
    from evaluating something on the side."""
    import inspect as py_inspect

    for module in (inspect, doctor):
        source = py_inspect.getsource(module)
        assert "from .engine" not in source
        assert "import engine" not in source


# ---------------------------------------------------------------------------
# explain
# ---------------------------------------------------------------------------


def test_every_outcome_has_an_explanation():
    """An outcome the engine can produce and nobody can look up is a word the
    reader has to guess at."""
    from m365_governance import explaining

    assert set(explaining.EXPLANATIONS) == set(Outcome)
    assert set(explaining.ORDER) == set(Outcome)


@pytest.mark.parametrize("name", [o.value for o in Outcome])
def test_explain_covers_every_section(capsys, name):
    code, out, _ = run(capsys, "explain", name)
    assert code == 0
    assert name.upper() in out
    for section in ("This is not", "How it aggregates", "In a pipeline", "Example"):
        assert section in out, f"{name} is missing the {section!r} section"


def _flat(text: str) -> str:
    """Assertions here are about content. The output is wrapped to a terminal
    width, so a sentence that reads correctly may still carry a line break in
    the middle of it."""
    return " ".join(text.split())


def test_explain_unknown_says_it_is_not_compliance(capsys):
    _, out, _ = run(capsys, "explain", "unknown")
    assert "This is not" in out
    assert "compliance" in _flat(out)
    assert "fact about the collection" in _flat(out)


def test_explain_separates_unknown_from_invalid_evidence(capsys):
    """The two are told apart by the fix, which is the useful distinction."""
    _, out, _ = run(capsys, "explain", "invalid-evidence")
    assert "collecting again" in _flat(out)
    assert "repairing the collector" in _flat(out)


def test_explain_says_error_is_about_the_engine(capsys):
    _, out, _ = run(capsys, "explain", "error")
    assert "describes the engine" in _flat(out)
    assert "may not write a message" in _flat(out)


def test_explain_all_covers_the_six(capsys):
    code, out, _ = run(capsys, "explain", "all")
    assert code == 0
    for outcome in Outcome:
        assert outcome.value.upper() in out
    assert "Nothing here aggregates as a pass except a pass." in out


def test_explain_rejects_a_name_that_is_not_an_outcome(capsys):
    with pytest.raises(SystemExit):
        run(capsys, "explain", "compliant")


def test_explain_does_not_break_a_flag_across_lines(capsys):
    """A flag split at a hyphen is a flag nobody can copy."""
    _, out, _ = run(capsys, "explain", "all")
    assert "--fail-\non" not in out
    assert "--fail-on-regression" in out


def test_explain_matches_what_the_pipeline_actually_does(capsys):
    """The text claims exit codes. This checks the claims against the code."""
    _, out, _ = run(capsys, "explain", "unknown")
    assert "--fail-on unresolved` exits non-zero" in _flat(out)

    code, _, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--evidence",
        str(FIXTURES / "site-owners-not-collected.json"),
        "--fail-on",
        "unresolved",
        "--format",
        "json",
    )
    assert code == 1

    code, _, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--evidence",
        str(FIXTURES / "site-owners-not-collected.json"),
        "--fail-on",
        "fail",
        "--format",
        "json",
    )
    assert code == 0, "explain says --fail-on fail ignores unknown; it does not"


# ---------------------------------------------------------------------------
# imported evidence, in the report
# ---------------------------------------------------------------------------


def test_an_imported_report_says_completeness_cannot_be_verified(capsys):
    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--evidence",
        str(FIXTURES / "site-imported-inventory.json"),
    )
    assert code == 0
    assert "Collection completeness cannot be verified" in _flat(out)
    assert "ShareGate Desktop" in out


def test_the_import_warning_comes_before_the_first_finding(capsys):
    """As prominent as the delegated one, and for a stronger reason: we did
    not choose the scope of that export and cannot reproduce it."""
    _, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--evidence",
        str(FIXTURES / "site-imported-inventory.json"),
    )
    assert out.index("imported evidence") < out.index("## Summary")


def test_the_html_report_carries_the_import_warning():
    html = to_html(_run_for("site-imported-inventory"))
    assert "Collection completeness cannot be verified" in html
    assert html.index("imported evidence") < html.index('class="card')


def test_a_stale_export_is_named_in_days():
    """The facts can be older than the file that carries them, and the reader
    is the last person able to notice."""
    text = to_markdown(_run_for("site-imported-inventory"))
    assert "14 days older than the export" in _flat(text)


def test_no_gap_is_reported_when_the_export_is_same_day():
    from m365_governance.reporting import _export_gap

    assert not _export_gap(
        {
            "collected_at": "2026-06-30T09:00:00Z",
            "import_source": {"exported_at": "2026-06-30T18:00:00Z"},
        }
    )


def test_stats_says_an_import_cannot_be_verified_here(capsys):
    _, out, _ = run(capsys, "stats", str(FIXTURES / "site-imported-inventory.json"))
    assert "imported" in out
    assert "cannot be verified by this engine" in _flat(out)


def test_the_default_profile_runs_every_rule():
    """It once enumerated them, and the enumeration went stale the first time a
    rule was added: two rules were written, validated, tested, and silently
    filtered out of every evaluation."""
    import yaml

    from m365_governance.loader import load_rules

    profile = yaml.safe_load((DATA / "profiles" / "default.yaml").read_text())
    assert "rules" not in profile, (
        "the default profile selects rules by name again. An absent selection "
        "means every rule; a list means the next rule added is excluded in "
        "silence."
    )

    on_disk = {loaded.data["id"] for loaded in load_rules(DATA / "rules")}
    ran = {
        result.rule_id
        for result in evaluate(
            [loaded.data for loaded in load_rules(DATA / "rules")],
            evidence("list-within-limit"),
        ).results
    }
    lists_only = {
        loaded.data["id"]
        for loaded in load_rules(DATA / "rules")
        if loaded.data["resource_type"] == "list"
    }
    assert ran == lists_only, f"rules on disk: {on_disk}, evaluated: {ran}"


# ---------------------------------------------------------------------------
# the support link, and where it may not appear
# ---------------------------------------------------------------------------

SUPPORT = ("buymeacoffee", "buy me a coffee", "sponsor", "donate", "support the")


def test_no_command_asks_for_support(capsys):
    """A person running a governance check is reading a finding. Nothing in
    that moment should be asking them for anything.

    It does not live anywhere in this repository either. The product explains
    the software and asks for nothing; support for the writing and the research
    is on ph7x.com, where what is being supported is the publishing.
    """
    invocations = [
        ["list-rules", "--rules", str(RULES)],
        ["show-rule", "SPO-SITE-001", "--rules", str(RULES)],
        ["explain", "all"],
        ["doctor"],
        ["stats", str(FIXTURES / "site-two-owners.json")],
        ["validate", "--rules", str(RULES)],
        [
            "evaluate",
            "--rules",
            str(RULES),
            "--evidence",
            str(FIXTURES / "list-over-limit.json"),
        ],
        [
            "evaluate",
            "--rules",
            str(RULES),
            "--evidence",
            str(FIXTURES / "list-over-limit.json"),
            "--format",
            "html",
        ],
        # `diff` needs two assessments, so its refusal is what this reads.
        # A message printed when somebody used a command wrongly is exactly
        # where a request for support would end up.
        [
            "diff",
            str(FIXTURES / "site-two-owners.json"),
            str(FIXTURES / "site-one-owner.json"),
        ],
    ]
    for argv in invocations:
        _, out, err = run(capsys, *argv)
        haystack = (out + err).lower()
        for word in SUPPORT:
            assert word not in haystack, f"{argv[0]} mentions {word!r}"


def test_no_report_asks_for_support():
    """Including the HTML one, which is the format most likely to be sent on
    to somebody who did not run the tool."""
    for fixture in ("list-over-limit", "site-owners-not-collected", "pass"):
        try:
            run_result = _run_for(fixture)
        except FileNotFoundError:
            continue
        for rendered in (to_markdown(run_result), to_html(run_result)):
            for word in SUPPORT:
                assert word not in rendered.lower()


def test_the_product_repository_asks_for_nothing():
    """The inverse of what this used to assert.

    It required the support link to be in the README, in CONTRIBUTING and in a
    FUNDING.yml, which was right while the decision was that it belonged here.
    The decision was that it belongs on the site: the product repository
    explains the software, documents how it is licensed today, and asks for
    nothing.
    """
    for name in ("README.md", "CONTRIBUTING.md"):
        text = (ROOT / name).read_text().lower()
        for word in SUPPORT:
            assert word not in text, f"{name} asks for support: {word}"

    assert not (ROOT / ".github" / "FUNDING.yml").exists(), (
        "a FUNDING.yml renders a Sponsor button on the repository page"
    )


def test_no_rule_or_schema_mentions_support():
    """A rule is a claim about a tenant. Nothing else belongs in one."""
    from m365_governance.loader import load_rules

    for loaded in load_rules(DATA / "rules"):
        text = loaded.path.read_text().lower()
        for word in SUPPORT:
            assert word not in text, f"{loaded.path.name} mentions {word!r}"


# ---------------------------------------------------------------------------
# collect: reads a tenant, judges nothing
# ---------------------------------------------------------------------------


def test_collect_never_evaluates_a_rule():
    """The separation is the point. A command that collected and judged in one
    step would produce a conclusion nobody could reproduce without the tenant
    in front of them."""
    import inspect as py_inspect

    from m365_governance import collecting

    source = py_inspect.getsource(collecting)
    for forbidden in ("from .engine", "from .validator", "import engine"):
        assert forbidden not in source, f"collecting imports {forbidden}"


def test_every_slice_names_the_profile_that_reads_it(capsys):
    """A collection paired with the wrong rules produces a wall of `unknown`
    for facts nobody requested."""
    from m365_governance import collecting

    profiles = {p.stem for p in (DATA / "profiles").glob("*.yaml")}
    for chosen in collecting.SLICES.values():
        assert chosen.profile in profiles, (
            f"slice {chosen.name} points at profile {chosen.profile}, "
            f"which does not exist. Profiles: {sorted(profiles)}"
        )


def test_a_dry_run_reaches_no_tenant(capsys, tmp_path):
    code, out, _ = run(
        capsys,
        "collect",
        "sharing",
        "--client-id",
        "00000000-0000-0000-0000-000000000000",
        "--site-url",
        "https://contoso.sharepoint.com",
        "--tenant-url",
        "https://contoso-admin.sharepoint.com",
        "--output",
        str(tmp_path / "e.json"),
        "--dry-run",
    )
    assert code == 0
    assert "-Mode SiteSharing" in out
    assert not (tmp_path / "e.json").exists()


@pytest.mark.parametrize(
    "slice_name,missing",
    [
        ("sites", "--tenant-url"),
        ("permissions", "--site-url"),
        # Sharing needs both: the settings are a tenant property about a site.
        ("sharing", "--tenant-url"),
    ],
)
def test_collect_refuses_without_the_url_it_needs(
    capsys, tmp_path, slice_name, missing
):
    argv = [
        "collect",
        slice_name,
        "--client-id",
        "00000000-0000-0000-0000-000000000000",
        "--output",
        str(tmp_path / "out"),
    ]
    if missing != "--site-url":
        argv += ["--site-url", "https://contoso.sharepoint.com"]
    code, _, err = run(capsys, *argv)
    assert code == 2
    assert missing in err


def test_the_collector_command_line_never_carries_a_write_flag(tmp_path):
    from m365_governance import collecting

    for name in collecting.SLICES:
        outcome = collecting.run_slice(
            name,
            client_id="00000000-0000-0000-0000-000000000000",
            output=tmp_path / "out",
            site_url="https://contoso.sharepoint.com",
            tenant_url="https://contoso-admin.sharepoint.com",
            dry_run=True,
        )
        for flag in ("-Force", "-Confirm:$false", "-WhatIf:$false", "-Set", "-Remove"):
            assert flag not in outcome.stdout, f"{name} passes {flag}"


# ---------------------------------------------------------------------------
# profiles select, and never judge
# ---------------------------------------------------------------------------


def test_no_profile_overrides_a_basis_or_a_severity():
    """A profile selects. The moment one restates a rule, results stop being
    comparable across profiles and the basis gets reviewed twice."""
    import yaml

    for path in sorted((DATA / "profiles").glob("*.yaml")):
        profile = yaml.safe_load(path.read_text()) or {}
        # `set_aside_classes` is presentation: it moves a resource down the
        # page and changes no outcome. Anything beyond this set would be a
        # profile restating a rule.
        allowed = {"name", "description", "rules", "set_aside_classes"}
        assert set(profile) <= allowed, (
            f"{path.name} carries more than a selection: "
            f"{sorted(set(profile) - allowed)}"
        )


def test_every_profile_selects_rules_that_exist():
    import yaml

    from m365_governance.loader import load_rules

    known = {loaded.data["id"] for loaded in load_rules(DATA / "rules")}
    for path in sorted((DATA / "profiles").glob("*.yaml")):
        profile = yaml.safe_load(path.read_text()) or {}
        for rule_id in profile.get("rules") or []:
            assert rule_id in known, (
                f"{path.name} selects {rule_id}, which does not exist"
            )


def test_a_profile_cuts_the_noise_without_hiding_a_finding(capsys):
    """Selecting fewer rules must remove `unknown`, never a `fail`."""
    everything = _run_for("site-sharing-anyone-default-anyone")
    fails = {r.rule_id for r in everything.results if r.outcome is Outcome.FAIL}

    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--profile",
        str(DATA / "profiles" / "sharing.yaml"),
        "--evidence",
        str(FIXTURES / "site-sharing-anyone-default-anyone.json"),
        "--format",
        "json",
    )
    assert code == 0
    selected = json.loads(out)
    kept = {r["rule_id"] for r in selected["results"] if r["outcome"] == "fail"}
    assert kept == fails
    assert selected["counts"]["unknown"] == 0


def test_each_slice_is_paired_with_a_profile_that_can_answer_it():
    """A slice pointing at the wrong profile produces a wall of `unknown`.

    The first pairing written was wrong: `sites` gathers inventory, not
    owners, and against the ownership profile it produced 106 `unknown`
    results across 53 real sites. Every one of them was honest and none of
    them was useful.
    """
    import yaml

    from m365_governance import collecting
    from m365_governance.loader import load_rules

    on_disk = {loaded.data["id"]: loaded.data for loaded in load_rules(RULES)}

    for chosen in collecting.SLICES.values():
        if not chosen.produces_findings:
            continue  # inventory slice; the test below covers it instead
        profile = yaml.safe_load(
            (DATA / "profiles" / f"{chosen.profile}.yaml").read_text()
        )
        # A profile with no `rules` key selects everything, which is what
        # `default` is for. Reading that as an empty selection would let a
        # slice paired with it pass this test by evaluating nothing at all.
        chosen_ids = profile.get("rules") or sorted(on_disk)
        selected = [on_disk[r] for r in chosen_ids]
        outcomes = [
            result.outcome
            for result in evaluate(selected, evidence(chosen.shaped_like)).results
        ]
        assert outcomes, (
            f"slice {chosen.name} with profile {chosen.profile}: no rule even "
            f"applies to a {chosen.shaped_like} document"
        )
        assert any(o is not Outcome.UNKNOWN for o in outcomes), (
            f"slice {chosen.name} paired with profile {chosen.profile} answers "
            f"nothing about its own evidence: {[o.value for o in outcomes]}"
        )


def test_a_slice_no_rule_consumes_says_what_does():
    """The twin rule, kept honest for the exception.

    A collection path no rule reads is normally forbidden, because it costs
    maintenance and produces nothing. One slice is deliberately outside that,
    and the price of the exception is naming its consumer: without it, the
    next reader cannot tell a considered decision from an oversight.
    """
    from m365_governance import collecting

    for chosen in collecting.SLICES.values():
        if chosen.produces_findings:
            assert chosen.consumed_by == "governance rules", (
                f"slice {chosen.name} produces findings, so its consumer is "
                f"the rules; it names {chosen.consumed_by!r}."
            )
            continue
        assert chosen.consumed_by != "governance rules", (
            f"slice {chosen.name} collects evidence no rule reads and names "
            f"the rules as its consumer. Say what actually reads it."
        )
        assert len(chosen.consumed_by) > 12, (
            f"slice {chosen.name} names its consumer as "
            f"{chosen.consumed_by!r}, which explains nothing."
        )


# ---------------------------------------------------------------------------
# classification: a label, never a filter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("list-class-content", "content"),
        ("list-class-catalog", "system"),
        ("list-class-system", "system"),
        ("list-class-application", "application"),
        # Never `content`. A list nobody classified is a list nobody looked at.
        ("list-class-unknown", "unknown"),
    ],
)
def test_a_list_is_classified_from_facts_the_product_reports(fixture, expected):
    from m365_governance.classifying import classify

    result = classify(evidence(fixture))
    assert result.kind.value == expected
    assert result.because, "a classification with no stated reason is a label to trust"


def test_classification_never_changes_an_outcome():
    """The label groups a report. It decides nothing."""
    from m365_governance.loader import load_rules

    rules = [loaded.data for loaded in load_rules(RULES)]
    plain = evaluate(rules, evidence("list-scopes-over-hard-limit"))
    labelled = evaluate(rules, evidence("list-catalog-over-hard-limit"))

    def outcomes(run):
        return {r.rule_id: r.outcome for r in run.results}

    assert outcomes(plain) == outcomes(labelled)
    assert labelled.resource_class == "system"


def test_setting_aside_cannot_hide_a_failure(capsys, tmp_path):
    """The reason this is `set_aside` and not `exclude`.

    A document library holding 61,400 unique permission scopes is over a hard
    product limit whoever created it, and SharePoint calling it a catalog is
    not a reason for a governance report to stay silent.
    """
    import shutil

    for name in ("list-catalog-over-hard-limit", "list-class-content"):
        shutil.copy(FIXTURES / f"{name}.json", tmp_path / f"{name}.json")

    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--profile",
        str(DATA / "profiles" / "capacity.yaml"),
        "--evidence",
        str(tmp_path),
        "--format",
        "markdown",
    )
    assert code == 0
    assert "Set aside by profile" in out
    # Counted in the summary, not only printed at the bottom.
    assert "| Fail | 2 |" in out
    assert "61400 unique permission scopes" in out
    assert "Nothing was removed" in out


def test_a_set_aside_resource_is_still_evaluated(capsys, tmp_path):
    import json as _json
    import shutil

    shutil.copy(FIXTURES / "list-catalog-over-hard-limit.json", tmp_path / "one.json")
    code, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--profile",
        str(DATA / "profiles" / "capacity.yaml"),
        "--evidence",
        str(tmp_path),
        "--format",
        "json",
    )
    assert code == 0
    payload = _json.loads(out)
    assert payload["set_aside"] == 1
    assert payload["counts"]["fail"] == 2
    assert payload["by_class"]["system"] == 1


def test_the_report_counts_resources_by_class(capsys, tmp_path):
    import shutil

    for name in (
        "list-class-content",
        "list-class-catalog",
        "list-class-system",
        "list-class-application",
    ):
        shutil.copy(FIXTURES / f"{name}.json", tmp_path / f"{name}.json")

    _, out, _ = run(
        capsys,
        "evaluate",
        "--rules",
        str(RULES),
        "--profile",
        str(DATA / "profiles" / "capacity.yaml"),
        "--evidence",
        str(tmp_path),
    )
    assert "4 resources observed" in out
    assert "content         1" in out
    assert "system          2" in out
    assert "application     1" in out


def test_no_profile_excludes_anything():
    """`set_aside_classes` is the only class key, and it is not `exclude`."""
    import yaml

    for path in sorted((DATA / "profiles").glob("*.yaml")):
        profile = yaml.safe_load(path.read_text()) or {}
        for forbidden in ("exclude_classes", "exclude", "skip", "ignore"):
            assert forbidden not in profile, (
                f"{path.name} carries {forbidden!r}. A profile moves a "
                f"resource down the page; it never removes one."
            )


def test_a_list_that_is_both_system_and_application_is_application():
    """Site Pages and Site Assets come back with both flags set on a real
    tenant. They were provisioned by the platform and they hold the pages of
    the site. Reading `is_system` first labelled them plumbing and moved a
    site's own pages down the report."""
    from m365_governance.classifying import classify

    result = classify(evidence("list-class-system-and-application"))
    assert result.kind.value == "application"
    assert "is_system is too" in result.because


def test_a_catalog_stays_system_even_when_it_is_also_a_system_list():
    """Style Library comes back as both on a real tenant. Catalog wins, and
    the answer is the same either way, which is why the order was safe to
    change for the other pair."""
    from m365_governance.classifying import classify

    facts = evidence("list-class-catalog")["facts"]["list"]
    assert facts["is_catalog"]["value"] is True
    assert facts["is_system"]["value"] is True
    assert classify(evidence("list-class-catalog")).kind.value == "system"


def test_content_is_never_assigned_by_absence():
    """Every `content` verdict must rest on three observed `false` values."""
    from m365_governance.classifying import classify

    for fixture in ("list-class-content", "list-class-unknown"):
        document = evidence(fixture)
        result = classify(document)
        if result.kind.value == "content":
            block = document["facts"]["list"]
            for name in ("is_catalog", "is_system", "is_application"):
                assert block[name]["state"] == "observed", (
                    f"{fixture} was called content while {name} was not observed"
                )


# ---------------------------------------------------------------------------
# assess and verify: the two halves of handing a result to somebody else
# ---------------------------------------------------------------------------


def three_resources(tmp_path):
    """An evidence directory with three distinct resources in it.

    Distinct on purpose: the whole fixture set describes the same site many
    times over, and a run set refuses two documents about one resource rather
    than averaging them.
    """
    folder = tmp_path / "evidence"
    folder.mkdir(parents=True)
    for name in ("site-agents-with-sources", "site-spfx-current", "list-class-content"):
        (folder / f"{name}.json").write_text(
            (FIXTURES / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
    return folder


def assessed(capsys, tmp_path, *extra) -> dict:
    out = tmp_path / "assessment.json"
    code, _, err = run(
        capsys,
        "assess",
        "--evidence",
        str(three_resources(tmp_path)),
        "--created-at",
        "2026-08-09T10:00:00Z",
        "--out",
        str(out),
        *extra,
    )
    assert code == 0, err
    return json.loads(out.read_text(encoding="utf-8"))


def test_assess_writes_something_verify_accepts(capsys, tmp_path):
    document = assessed(capsys, tmp_path)
    path = tmp_path / "assessment.json"

    code, out, err = run(capsys, "verify", str(path))
    assert code == 0, err
    assert document["canonical"]["manifest"]["assessment_id"] in out
    assert "contoso.sharepoint.com" in out


def test_the_same_inputs_produce_the_same_assessment(capsys, tmp_path):
    """`--created-at` exists for this. An identity that moved because time
    passed would make an assessment unverifiable by construction, and nobody
    could rebuild one to check a claim about it."""
    first = assessed(capsys, tmp_path)
    second = assessed(capsys, tmp_path / "again")
    assert (
        first["canonical"]["manifest"]["assessment_id"]
        == second["canonical"]["manifest"]["assessment_id"]
    )


def test_verify_refuses_an_assessment_that_was_edited(capsys, tmp_path):
    assessed(capsys, tmp_path)
    path = tmp_path / "assessment.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["canonical"]["manifest"]["tenant"] = "somebody-elses.sharepoint.com"
    path.write_text(json.dumps(document), encoding="utf-8")

    code, _, err = run(capsys, "verify", str(path))
    assert code == 1
    assert "digest" in err


def test_verify_says_what_a_report_is_rather_than_crashing(capsys, tmp_path):
    """A stored run is not an assessment, and telling somebody which command
    they wanted costs one sentence."""
    stored = tmp_path / "run.json"
    stored.write_text(json.dumps(_run_for("site-spfx-current").to_dict()), "utf-8")

    code, _, err = run(capsys, "verify", str(stored))
    assert code == 2
    assert "report" in err


def test_the_manifest_cannot_claim_a_tenant_the_evidence_denies(capsys, tmp_path):
    """Two collections of two different tenants in one directory. The refusal
    is the point: every count in one summary would be a sum across estates
    nobody manages together."""
    folder = three_resources(tmp_path)
    stray = json.loads((FIXTURES / "site-modern-clean.json").read_text())
    stray["provenance"]["tenant"]["host"] = "fabrikam.sharepoint.com"
    (folder / "stray.json").write_text(json.dumps(stray), encoding="utf-8")

    code, _, err = run(capsys, "assess", "--evidence", str(folder))
    assert code == 2
    assert "more than one host" in err


def test_an_assessment_renders_and_compares_like_what_it_carries(capsys, tmp_path):
    """`report` and `diff` take one because an assessment is what somebody was
    sent. Neither reads anything under `derived`: a report that could not be
    regenerated from the canonical half would be a second original."""
    assessed(capsys, tmp_path)
    path = str(tmp_path / "assessment.json")

    code, out, err = run(capsys, "report", path)
    assert code == 0, err
    assert "3 resources observed" in out

    code, out, err = run(capsys, "diff", path, path)
    assert code == 0, err
    assert "Nothing changed" in out
