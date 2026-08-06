"""The commands that read, and the two that re-read a conclusion.

None of these reaches a new conclusion, and that is the property worth
testing: `list-rules`, `show-rule`, `doctor` and `stats` never evaluate, and
`report` and `diff` never re-evaluate what was already decided.
"""

from __future__ import annotations

import json

import pytest

from conftest import FIXTURES, ROOT, evidence, rule
from m365_governance import diffing, doctor, inspect
from m365_governance.cli import main
from m365_governance.engine import evaluate
from m365_governance.reporting import to_html
from m365_governance.results import Outcome, Run

RULES = ROOT / "rules"


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _run_for(fixture: str) -> Run:
    return evaluate([rule("SPO-SITE-001"), rule("SPO-LIST-001")], evidence(fixture))


# ---------------------------------------------------------------------------
# list-rules
# ---------------------------------------------------------------------------


def test_list_rules_names_the_kind_of_claim(capsys):
    code, out, _ = run(capsys, "list-rules", "--rules", str(RULES))
    assert code == 0
    assert "SPO-LIST-001" in out and "SPO-SITE-001" in out
    assert "documented-limit" in out and "convention" in out
    assert "2 rules" in out


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


def test_doctor_is_healthy_on_this_repository(capsys):
    code, out, _ = run(capsys, "doctor", "--root", str(ROOT))
    assert code == 0
    assert "Nothing is broken." in out


def test_doctor_reports_what_it_found_and_not_only_that_it_liked_it(capsys):
    _, out, _ = run(capsys, "doctor", "--root", str(ROOT))
    import platform

    assert platform.python_version() in out
    assert "rule.schema.json" in out


def test_doctor_fails_when_a_rule_is_broken(tmp_path):
    """A rule that does not validate is a broken installation, not a warning."""
    import shutil

    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    shutil.copytree(ROOT / "profiles", tmp_path / "profiles")
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

    shutil.copytree(ROOT / "rules", tmp_path / "rules")
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


def test_diff_reports_the_movement_and_the_evidence_behind_it(capsys):
    code, out, _ = run(
        capsys,
        "diff",
        str(FIXTURES / "site-two-owners.json"),
        str(FIXTURES / "site-one-owner.json"),
        "--rules",
        str(RULES),
    )
    assert code == 0
    assert "pass → fail" in out
    assert "`owners.count` | 2 | 1" in out


def test_diff_is_quiet_when_nothing_moved(capsys):
    code, out, _ = run(
        capsys,
        "diff",
        str(FIXTURES / "site-two-owners.json"),
        str(FIXTURES / "site-two-owners.json"),
        "--rules",
        str(RULES),
    )
    assert code == 0
    assert "Nothing changed" in out


def test_diff_says_when_the_rule_moved_and_not_only_the_estate():
    """The question an audit asks is whether the estate changed or we did."""
    before = _run_for("site-one-owner")
    after = _run_for("site-one-owner")
    after.results[0].rule_version = "9.9"

    text = diffing.to_markdown(before, after)
    assert "The rule changed too" in text
    assert "may be the rule rather than the estate" in text


def test_diff_does_not_call_a_disappeared_rule_a_pass():
    before = _run_for("site-one-owner")
    after = _run_for("site-one-owner")
    after.results = []

    text = diffing.to_markdown(before, after)
    assert "A rule that stopped running is not a rule that passed" in text


def test_diff_can_fail_a_pipeline_on_a_regression(capsys):
    code, _, _ = run(
        capsys,
        "diff",
        str(FIXTURES / "site-two-owners.json"),
        str(FIXTURES / "site-one-owner.json"),
        "--rules",
        str(RULES),
        "--fail-on-regression",
    )
    assert code == 1


def test_a_regression_into_unknown_also_fails(capsys):
    """Leaving `pass` for `unknown` is a regression: the answer was lost."""
    code, _, _ = run(
        capsys,
        "diff",
        str(FIXTURES / "site-two-owners.json"),
        str(FIXTURES / "site-owners-not-collected.json"),
        "--rules",
        str(RULES),
        "--fail-on-regression",
    )
    assert code == 1


def test_diff_accepts_a_stored_report_on_either_side(capsys, tmp_path):
    stored = tmp_path / "before.json"
    stored.write_text(json.dumps(_run_for("site-two-owners").to_dict()))

    code, out, _ = run(
        capsys,
        "diff",
        str(stored),
        str(FIXTURES / "site-one-owner.json"),
        "--rules",
        str(RULES),
    )
    assert code == 0
    assert "pass → fail" in out


def test_diff_rejects_a_file_that_is_neither(capsys, tmp_path):
    junk = tmp_path / "junk.json"
    junk.write_text('{"hello": "world"}')
    code, _, err = run(capsys, "diff", str(junk), str(junk), "--rules", str(RULES))
    assert code == 2
    assert "neither a report" in err


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
        ["doctor", "--root", str(ROOT)],
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
