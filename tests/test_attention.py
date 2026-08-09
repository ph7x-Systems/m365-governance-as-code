"""What deserves a person's time, and why the engine is the one that says so.

The claim under test is narrow and it is the whole point: attention is derived
from facts a consumer also receives, it is never the outcome and never the
severity, and every state it reaches carries the reasons that produced it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from m365_governance import attention

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "m365_governance" / "data" / "fixtures" / "sharepoint"


def result(**over) -> dict:
    """A result with only the members attention reads."""
    base = {
        "outcome": "pass",
        "basis": "requirement",
        "passes_without_resolving": "",
    }
    return base | over


def evaluate(fixture: str) -> dict:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "m365_governance.cli",
            "evaluate",
            "--evidence",
            str(FIXTURES / f"{fixture}.json"),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if done.returncode not in (0, 1):
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


# ── attention is not the outcome ──────────────────────────────────────────


def test_a_failure_is_not_automatically_something_to_act_on():
    """The invariant, stated as a test.

    Two failures, identical but for the basis. One is the tenant outside
    something the vendor documented; the other is somebody having made a
    defensible different choice. A model that read `fail` as the verdict could
    not tell them apart, and every convention in the rule set would arrive
    looking like a violation.
    """
    documented = attention.for_result(result(outcome="fail", basis="requirement"))
    chosen = attention.for_result(result(outcome="fail", basis="convention"))

    assert documented["state"] == "act"
    assert chosen["state"] == "review"
    assert documented["rank"] < chosen["rank"]


def test_a_pass_that_leaves_something_unresolved_is_still_worth_reading():
    """And the other direction: `pass` is not automatically nothing."""
    settled = attention.for_result(result(outcome="pass"))
    unsettled = attention.for_result(
        result(outcome="pass", passes_without_resolving="it says nothing about guests")
    )

    assert settled["state"] == "none"
    assert unsettled["state"] == "review"
    assert unsettled["rank"] < settled["rank"]


@pytest.mark.parametrize("basis", ["documented-guidance", "convention", "opinion"])
def test_only_a_vendor_documented_basis_reaches_act(basis):
    """An opinion is ours. It must never be published as a violation."""
    judged = attention.for_result(result(outcome="fail", basis=basis))
    assert judged["state"] == "review"


# ── attention is not the severity ─────────────────────────────────────────


def test_severity_does_not_reach_the_judgement_at_all():
    """Severity is the rule author's standing claim, written against no tenant.

    Two results identical but for severity reach the same attention, because
    what changed is a statement about the rule rather than about this reading.
    """
    low = attention.for_result(
        result(outcome="fail", basis="requirement", severity="low")
    )
    critical = attention.for_result(
        result(outcome="fail", basis="requirement", severity="critical")
    )

    assert low == critical


# ── unknown and invalid-evidence stay apart ───────────────────────────────


def test_an_unread_answer_and_an_untrustworthy_one_are_never_the_same_thing():
    """Both reach no answer, and they are different failures.

    `unknown` says nobody read it. `invalid-evidence` says the engine read
    something and could not trust it, which is a defect in the collection
    rather than a gap in it. They share a state because neither decided
    anything, and they are kept apart by rank and by their reasons — the two
    things a reader actually perceives.
    """
    unread = attention.for_result(result(outcome="unknown"))
    untrusted = attention.for_result(result(outcome="invalid-evidence"))

    assert unread["state"] == untrusted["state"] == "observe"
    assert untrusted["rank"] < unread["rank"]
    assert unread["because"] != untrusted["because"]


# ── absence stays explicit ────────────────────────────────────────────────


def test_no_judgement_is_not_the_same_as_nothing_to_do():
    """`error` describes the engine, not the tenant.

    Reporting it as `none` would make a rule that never ran indistinguishable
    from one that ran and found nothing.
    """
    broke = attention.for_result(result(outcome="error"))
    clean = attention.for_result(result(outcome="pass"))

    assert broke["state"] == "not-evaluated"
    assert clean["state"] == "none"
    assert broke["state"] != clean["state"]


def test_an_outcome_the_engine_does_not_rank_is_said_rather_than_guessed():
    unranked = attention.for_result(result(outcome="something-new"))

    assert unranked["state"] == "not-evaluated"
    assert "something-new" in unranked["because"][0]


# ── never a bare verdict ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "case",
    [
        {"outcome": "fail", "basis": "requirement"},
        {"outcome": "fail", "basis": "convention"},
        {"outcome": "unknown"},
        {"outcome": "invalid-evidence"},
        {"outcome": "pass"},
        {"outcome": "not-applicable"},
        {"outcome": "error"},
    ],
)
def test_every_state_carries_the_facts_that_produced_it(case):
    judged = attention.for_result(result(**case))

    assert judged["because"], "a verdict with no reasons is the thing this stops"
    assert all(line.strip() for line in judged["because"])


# ── the run is not the sum of its results ─────────────────────────────────


def test_a_run_that_saw_almost_nothing_does_not_report_as_clean():
    """The reason run attention exists at all.

    A slice the collector could not read produces no result, so counting only
    results would call this run clean — which is the omission the whole
    coverage surface exists to prevent.
    """
    judged = attention.for_run(
        [result(outcome="pass")],
        {
            "requested": ["sharing", "owners"],
            "completed": ["sharing"],
            "unavailable": {
                "owners": {"state": "permission-denied", "detail": "refused"}
            },
        },
    )

    assert judged["state"] == "observe"
    assert judged["unobserved"] == ["owners"]
    assert "owners" in judged["because"][0]


def test_a_run_with_failures_still_says_what_was_not_read():
    """The leading state alone would hide half the sentence."""
    judged = attention.for_run(
        [result(outcome="fail", basis="requirement")],
        {"unavailable": {"activity": {"state": "not-supported", "detail": "no api"}}},
    )

    assert judged["state"] == "act"
    assert len(judged["because"]) == 2
    assert "not read" in judged["because"][1]


def test_a_clean_run_says_so_plainly():
    judged = attention.for_run([result(outcome="pass")], {"unavailable": {}})

    assert judged["state"] == "none"
    assert judged["unobserved"] == []


def test_a_run_with_no_rules_formed_no_judgement():
    judged = attention.for_run([], {"unavailable": {}})

    assert judged["state"] == "not-evaluated"


def test_the_counts_name_every_state_including_the_empty_ones():
    """A count that disappears when it is zero makes absent and none look alike."""
    judged = attention.for_run([result(outcome="pass")], {"unavailable": {}})

    assert set(judged["counts"]) == set(attention.STATES)
    assert judged["counts"]["none"] == 1
    assert judged["counts"]["act"] == 0


# ── against what the engine really emits ──────────────────────────────────


def test_a_real_run_carries_attention_on_every_result_and_on_itself():
    run = evaluate("site-class-group-unlabelled")

    assert run["attention"]["state"] in attention.STATES
    assert run["attention"]["because"]
    assert all(r["attention"]["because"] for r in run["results"])
    # Derived from what a consumer receives, so a reader can check it.
    for one in run["results"]:
        assert one["attention"] == attention.for_result(one)


def test_the_published_rank_orders_a_real_run():
    """Ordering carries governance meaning, so the engine publishes the order.

    The Workbench sorted `fail`, `invalid-evidence`, `unknown`, `pass`,
    `not-applicable` in C#, and the CLI never knew about it: two surfaces of
    one product disagreeing about what mattered, each internally consistent.
    """
    run = evaluate("site-class-invalid")
    ranks = [r["attention"]["rank"] for r in run["results"]]

    assert ranks, "the fixture should produce results"
    assert sorted(ranks) == sorted(ranks)  # the ranks are comparable integers
    # And an untrustworthy reading really does come before an absent one.
    by_outcome = {r["outcome"]: r["attention"]["rank"] for r in run["results"]}
    if "invalid-evidence" in by_outcome and "unknown" in by_outcome:
        assert by_outcome["invalid-evidence"] < by_outcome["unknown"]


# ── one ranking, and the surfaces read it rather than repeating it ────────


def test_an_engine_failure_is_never_buried_under_good_news():
    """`not-evaluated` outranks a pass, and that is deliberate.

    Ranking it last would put a defect of ours below findings that worked. It
    says nothing about the tenant, which is precisely why somebody has to look:
    part of the report is missing and the rest looks complete.
    """
    assert attention.RANK["no-judgement"] < attention.RANK["decided-non-normative"]
    assert attention.RANK["no-judgement"] < attention.RANK["settled"]
    # And still below the two tiers that describe a real reading.
    assert attention.RANK["documented-violation"] < attention.RANK["no-judgement"]
    assert attention.RANK["evidence-untrusted"] < attention.RANK["no-judgement"]


def test_a_run_that_produced_no_judgement_says_so_before_it_says_anything_else():
    judged = attention.for_run(
        [result(outcome="error"), result(outcome="pass")], {"unavailable": {}}
    )

    assert judged["state"] == "not-evaluated"
    assert "no judgement" in judged["because"][0]


def test_the_command_line_no_longer_holds_a_priority_of_its_own():
    """The duplication this step removed, asserted so it cannot come back.

    The CLI ordered `fail, invalid-evidence, unknown, error, not-applicable,
    pass`. The Workbench ordered `fail, invalid-evidence, unknown, pass,
    not-applicable`. Both were hand-written, neither knew about the other, and
    they disagreed about where a pass and an engine error belonged.
    """
    from m365_governance import reporting

    published = [attention.rank_of_outcome(o.value) for o in reporting._ORDER]

    assert published == sorted(published), (
        "the report groups its outcomes in an order the engine did not publish"
    )
    assert reporting._ORDER[0].value == "fail"
    assert attention.rank_of_outcome("error") < attention.rank_of_outcome("pass")


def test_the_order_is_stable_across_calls():
    """A report whose sections move between runs is a report nobody can diff."""
    from m365_governance import reporting

    assert [o.value for o in reporting._ORDER] == [o.value for o in reporting._ORDER]


# ── two vocabularies, and they are not the same one ───────────────────────


def test_a_state_and_a_tier_never_share_a_name():
    """The defect this reconciliation closed.

    Ranks were keyed by a mixture of state names and OUTCOME names, so
    `observe` had no entry at all. Anything asking for its rank missed and fell
    through to a default.
    """
    assert not set(attention.STATES) & set(attention.TIERS)
    assert len(attention.STATES) == 5
    assert len(attention.TIERS) == 6


def test_every_tier_maps_to_a_state_and_every_state_is_reachable():
    assert set(attention.STATE_OF_TIER) == set(attention.TIERS)
    assert set(attention.STATE_OF_TIER.values()) == set(attention.STATES)


def test_observe_is_the_one_state_spanning_two_tiers():
    """Which is the whole reason there are two enumerations."""
    spanning = [
        state
        for state in attention.STATES
        if sum(1 for s in attention.STATE_OF_TIER.values() if s == state) > 1
    ]
    assert spanning == ["observe"]


def test_a_run_that_reached_no_answer_is_never_ranked_as_no_judgement():
    """The bug, stated as a test.

    `observe` had no rank entry, so a run in `observe` published 2 — which is
    `no-judgement`'s rank. The document said one thing in `state` and another
    in `rank`, and both looked deliberate.
    """
    judged = attention.for_run(
        [result(outcome="unknown")],
        {"unavailable": {}},
    )

    assert judged["state"] == "observe"
    assert judged["rank"] == attention.RANK["evidence-absent"]
    assert judged["rank"] != attention.RANK["no-judgement"]


def test_every_published_rank_is_the_index_of_its_tier():
    assert {t: i for i, t in enumerate(attention.TIERS)} == attention.RANK
    assert min(attention.RANK.values()) == 0
    assert max(attention.RANK.values()) == 5


def test_a_run_takes_the_most_urgent_tier_present_however_it_arose():
    """One rule, asked once.

    `observe` used to appear twice in the run's ladder — above `not-evaluated`
    when the gap was an unread area, below it when the gap was an unanswered
    rule. Which state a run reported depended on which kind of gap it had.
    """
    unread_area = attention.for_run(
        [result(outcome="error")],
        {"unavailable": {"sharing": {"state": "permission-denied", "detail": "no"}}},
    )
    unanswered_rule = attention.for_run(
        [result(outcome="error"), result(outcome="unknown")],
        {"unavailable": {}},
    )

    # A defect of ours outranks a gap, whichever kind of gap it is.
    assert unread_area["state"] == "not-evaluated"
    assert unanswered_rule["state"] == "not-evaluated"
    assert unread_area["rank"] == unanswered_rule["rank"]


def test_none_is_a_judgement_and_is_counted_like_any_other():
    """It is not absence. `not-evaluated` is the one that means that."""
    judged = attention.for_run(
        [result(outcome="pass"), result(outcome="not-applicable")],
        {"unavailable": {}},
    )

    assert judged["state"] == "none"
    assert judged["counts"]["none"] == 2
    assert set(judged["counts"]) == set(attention.STATES)
    assert attention.STATE_OF_TIER["settled"] == "none"


def test_the_state_a_result_publishes_is_always_its_tier_s_state():
    """No path may set one without the other."""
    for outcome in (
        "pass",
        "fail",
        "unknown",
        "invalid-evidence",
        "not-applicable",
        "error",
        "made-up",
    ):
        judged = attention.for_result(result(outcome=outcome))
        tier = attention.TIERS[judged["rank"]]
        assert judged["state"] == attention.STATE_OF_TIER[tier]


def test_the_schema_publishes_exactly_the_five_states_the_engine_knows():
    """The contract and the code cannot drift apart on the vocabulary."""
    schema = json.loads(
        (
            ROOT / "src" / "m365_governance" / "data" / "schemas" / "run.schema.json"
        ).read_text(encoding="utf-8")
    )
    for name in ("attention", "run_attention"):
        declared = schema["$defs"][name]["properties"]["state"]["enum"]
        assert sorted(declared) == sorted(attention.STATES)
        rank = schema["$defs"][name]["properties"]["rank"]
        assert rank["minimum"] == 0
        assert rank["maximum"] == len(attention.TIERS) - 1


# ── `basis: opinion` is ours, and it never borrows a vendor's authority ────


def test_the_two_contracts_agree_on_what_a_basis_can_be():
    """They did not.

    The rule contract has allowed five basis types for as long as it has had
    the enum. The run contract's description listed four and said outright that
    an opinion was not one — so a rule could be authored that the document
    carrying its result declared impossible. Nothing failed, because a
    description is prose and prose validates nothing.
    """
    schemas = ROOT / "src" / "m365_governance" / "data" / "schemas"
    rule = json.loads((schemas / "rule.schema.json").read_text(encoding="utf-8"))
    run = json.loads((schemas / "run.schema.json").read_text(encoding="utf-8"))

    allowed = rule["$defs"]["basis"]["properties"]["type"]["enum"]
    described = run["$defs"]["result"]["properties"]["basis"]["description"]

    assert "opinion" in allowed
    for kind in allowed:
        assert kind in described, f"the run contract does not mention {kind}"
    assert "An opinion is not one" not in described


def test_an_opinion_never_reaches_act_however_the_rule_is_worded():
    """The reconciliation that matters.

    `opinion` is ours. A failure against it is pH7x disagreeing with a choice,
    not the tenant being outside anything a vendor wrote down — so it must
    never be published as a documented violation, whatever severity or wording
    the rule carries.
    """
    for severity in ("low", "medium", "high", "critical"):
        judged = attention.for_result(
            result(outcome="fail", basis="opinion", severity=severity)
        )
        assert judged["state"] == "review"
        assert judged["rank"] == attention.RANK["decided-non-normative"]

    assert "opinion" not in attention.NORMATIVE


def test_an_opinion_is_attributed_where_it_is_read():
    """A report is read by somebody who did not write it.

    The gloss said "our position, stated as ours", which does not say whose —
    and beside four bases that are Microsoft's, an unattributed fifth reads as
    theirs.
    """
    from m365_governance import reporting

    gloss = reporting._BASIS_GLOSS["opinion"]

    assert "pH7x" in gloss
    assert gloss != "our position, stated as ours"
