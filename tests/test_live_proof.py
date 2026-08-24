"""The proof registry, and the direction it is only allowed to run in.

    real execution -> sanitized proof record -> validated -> live state

Never a state written first and a record produced to agree with it. These tests
hold that direction, hold the sanitization, and hold the one property the whole
thing exists for: **removing the proof removes the claim.**
"""

import json
import re

import pytest

from m365_governance import live_proof
from m365_governance.collecting import SLICES, Live

FORBIDDEN = re.compile(
    r"\.onmicrosoft\.com|\.sharepoint\.com|@[\w.-]+\.\w+"
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def registry():
    return json.loads(live_proof.REGISTRY.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# the direction
# ---------------------------------------------------------------------------


def test_a_collector_without_a_record_is_none(monkeypatch):
    """The absence of a record is the answer, not a gap to be filled in later.

    `customization` is the live case and it is why this registry exists: the
    collector's own source says a defect was found by provoking the state in a
    directory, and no record of that run survives. The state is `none`, and it
    stays `none` until something runs and leaves a record.
    """
    assert live_proof.established_state("customization") == "none"
    assert SLICES["customization"].live is Live.NONE


def test_removing_the_proof_removes_the_claim(monkeypatch):
    """THE NEGATIVE, WHICH IS THE ONLY PROOF THAT THIS IS DERIVED AT ALL.

    A property that happens to agree with a hand-written field is
    indistinguishable from the field. What distinguishes them is what happens
    when the proof goes away: `sites` is `full` today, and with its records
    withdrawn it is `none` -- not `full` with a warning, and not the previous
    value remembered from somewhere.
    """
    assert SLICES["sites"].live is Live.FULL

    kept = live_proof._registry()["records"]
    monkeypatch.setitem(
        live_proof._registry(),
        "records",
        [r for r in kept if r.get("collector") != "sites"],
    )

    assert live_proof.established_state("sites") == "none"
    assert SLICES["sites"].live is Live.NONE


def test_an_invalid_record_does_not_support_a_state(monkeypatch):
    """A record claiming something outside the vocabulary supports nothing.

    Not the nearest state, not the previous one. A record this engine cannot
    read is a record it does not count, which is the same rule it applies to a
    fact a rule cannot address.
    """
    monkeypatch.setitem(
        live_proof._registry(),
        "records",
        [{"collector": "sites", "establishes": "mostly-fine"}],
    )

    assert live_proof.established_state("sites") == "none"


def test_the_migrated_set_is_closed(registry):
    """The one provenance that may not grow.

    These records transcribe what was written down contemporaneously, before
    this registry existed. They are honest and they are weaker than a record an
    execution emitted: the artefacts are gone and several fields were never
    captured. Closing the set is what stops the forbidden direction from being
    available again -- from here on, the only way to raise a state is to run
    something.
    """
    migrated = [
        r for r in registry["records"] if r["provenance"] == live_proof.MIGRATED
    ]

    assert len(migrated) == 12, (
        "the migrated set is closed at the twelve records transcribed from "
        "docs/COLLECTOR-LIVE-MATRIX.md. A new record must be emitted by a run."
    )
    assert "THE SET IS CLOSED" in registry["_on_migration"]


def test_every_record_declares_a_known_provenance(registry):
    unknown = {
        r["collector"]: r.get("provenance")
        for r in registry["records"]
        if r.get("provenance") not in live_proof.PROVENANCES
    }

    assert not unknown, f"records with an unrecognised provenance: {unknown}"


# ---------------------------------------------------------------------------
# the sanitization
# ---------------------------------------------------------------------------


def test_no_record_carries_anything_that_identifies_a_tenant(registry):
    """A hostname, a principal name or a directory identifier, anywhere.

    The registry is committed and this repository is public. What proves a run
    happened is the method, the date, the identity KIND, the population as a
    count or a shape, the result and the limitations. None of that needs to say
    whose directory it was, and a record that said so would trade the thing the
    product promises for a detail nobody needs.
    """
    offending = [
        (r.get("collector"), hit.group(0))
        for r in registry["records"]
        for hit in [FORBIDDEN.search(json.dumps(r))]
        if hit
    ]

    assert not offending, f"records carrying tenant identifiers: {offending}"


def test_a_population_is_a_count_or_a_shape_and_never_a_list(registry):
    """`11 documents` proves the read. A list of eleven names publishes them."""
    listed = [
        r["collector"]
        for r in registry["records"]
        if isinstance(r.get("population"), list)
    ]

    assert not listed, f"records whose population is a list: {listed}"


# ---------------------------------------------------------------------------
# the digest, and exactly how much it proves
# ---------------------------------------------------------------------------


def test_a_record_without_a_digest_says_what_happened_to_the_artefact(registry):
    """An orphan digest and a silent absence are both overreach.

    `artifact_digest` proves CONTINUITY with the artefact observed at that
    moment. It does not permit revalidating an artefact that no longer exists,
    and where the artefact was deleted under the tenant-data rule the record
    says so plainly instead of leaving a reader to assume it could be checked.
    """
    silent = [
        r["collector"]
        for r in registry["records"]
        if not r.get("artifact_digest") and not r.get("artifact_disposition")
    ]

    assert not silent, (
        f"records with no digest and no disposition: {silent}. A missing digest "
        "is a fact about the artefact and has to be stated as one."
    )
    assert "does not permit revalidating" in registry["_on_the_digest"]


def test_every_record_carries_the_fields_a_proof_needs(registry):
    required = (
        "collector",
        "acquisition_method",
        "observed_at",
        "identity_kind",
        "population",
        "coverage",
        "result",
        "limitations",
        "contract_versions",
        "engine_version",
        "establishes",
        "provenance",
    )
    missing = {
        r.get("collector"): [f for f in required if f not in r]
        for r in registry["records"]
        if any(f not in r for f in required)
    }

    assert not missing, f"records missing required fields: {missing}"


# ---------------------------------------------------------------------------
# what a run leaves behind
# ---------------------------------------------------------------------------


class _FakeOutcome:
    """An execution that finished, without one having happened.

    The emission path is code and is tested as code. Nothing here reaches a
    directory, and the autouse guard in `conftest.py` would refuse it if it
    tried.
    """

    written = ("a.json", "b.json", "c.json")
    started_at = "2026-08-23T10:00:00Z"
    state = "completed"
    digest = "sha256:" + "ab" * 32


def test_a_run_leaves_a_record_that_carries_no_tenant():
    draft = live_proof.draft_from_run(
        _FakeOutcome(), collector="customization", acquisition_method="pnp-powershell"
    )

    assert not FORBIDDEN.search(json.dumps(draft)), (
        "the emitted record must be sanitized at the source; a step that "
        "sanitizes later is a step somebody skips"
    )
    assert draft["population"] == "3 documents", (
        "a count, never the things counted: the documents are tenant evidence"
    )
    assert draft["provenance"] == live_proof.EMITTED


def test_a_run_does_not_write_its_own_verdict():
    """A successful call is not a proved interpretation, and it may not say so.

    `establishes` is left empty on purpose. A run proves an acquisition; it
    does not prove that what came back was read correctly, and a collector that
    stamped its own `full` at the end of a successful call would be a claim
    produced by the thing it is a claim about -- which is exactly the shape
    this registry was built to remove.
    """
    draft = live_proof.draft_from_run(
        _FakeOutcome(), collector="customization", acquisition_method="pnp-powershell"
    )

    assert draft["establishes"] is None
    assert live_proof.established_state("customization") == "none"


def test_a_collection_writes_its_draft_beside_the_evidence(tmp_path, monkeypatch):
    """The step nobody has to remember, because it was forgotten once.

    A real directory corrected the `customization` collector and no record of
    that run exists. `docs/COLLECTOR-LIVE-MATRIX.md` still reads `not observed`
    for it, and the state cannot be raised on the strength of a source comment
    about a run nobody wrote down. That is the whole argument for emitting the
    draft from the run rather than asking a person to.

    Nothing here reaches a directory: the collection is stubbed at the boundary
    and the assertion is about what the run leaves on disk afterwards.
    """
    from m365_governance import collecting

    written = collecting.write_proof_draft(
        _FakeOutcome(), name="customization", output=tmp_path
    )

    assert written is not None and written.exists()
    draft = json.loads(written.read_text())

    assert draft["collector"] == "customization"
    assert draft["acquisition_method"] == "pnp-powershell"
    assert draft["establishes"] is None, (
        "a run does not write its own verdict; the steps between a successful "
        "acquisition and a proved interpretation are in LIVE-VALIDATION.md"
    )
    assert not FORBIDDEN.search(written.read_text())


def test_the_draft_does_not_land_inside_the_package(tmp_path):
    """It goes where the evidence went, which is the operator's machine.

    A draft written into `data/live-proof.json` would be a run editing the
    registry that governs it. The registry is changed by a person, on purpose,
    after reading the draft.
    """
    from m365_governance import collecting

    written = collecting.write_proof_draft(
        _FakeOutcome(), name="customization", output=tmp_path
    )

    assert tmp_path in written.parents
    assert "m365_governance" not in str(written)


# ---------------------------------------------------------------------------
# the stages, and the sentence they exist to make impossible
# ---------------------------------------------------------------------------


def test_a_stage_nobody_wrote_about_is_not_attempted(registry):
    """`bundle` and `consumer` are `not-attempted` on every migrated record.

    The matrix those records were transcribed from does not mention either
    one: no bundle produced from tenant evidence, no independent consumer
    opening it. That is not a gap to fill in from memory, and the temptation to
    round it up is precisely what this whole registry exists to refuse.
    """
    unwritten = {"bundle", "consumer"}
    claimed = {
        r["collector"]: {
            stage: state
            for stage, state in r["stages"].items()
            if stage in unwritten and state != "not-attempted"
        }
        for r in registry["records"]
        if r["provenance"] == live_proof.MIGRATED
    }
    offenders = {name: found for name, found in claimed.items() if found}

    assert not offenders, (
        f"migrated records claiming a stage the matrix never recorded: {offenders}"
    )


def test_nothing_is_vertical_path_proven_yet_and_the_product_says_so():
    """THE UNCOMFORTABLE ONE, and it is the point of the exercise.

    Nine collectors carry `full`, which in the published contract means *a real
    read produced real evidence*. It has never meant more. A presentation layer
    rendered that as READ FROM A TENANT, END TO END -- a wider sentence than
    the value supports, written by a layer that may explain a contract value
    and never widen it.

    With the stages separated, the honest count of capabilities proved along
    the whole vertical is zero, because nobody recorded a bundle produced from
    tenant evidence or a consumer opening one. This test pins that so the
    number cannot drift upward without records behind it, and it is expected to
    fail the day a real run proves one -- at which point the number moves
    because the record moved it.
    """
    grouped = live_proof.population()

    assert grouped["vertical-path-proven"] == [], (
        "a capability reached the top of the ladder; if a run proved it, this "
        "test is what tells the next person to check the record rather than "
        "the claim"
    )
    # `brand-center` joins it the day it is registered, and it is registered
    # before it has ever run. That is the right order: a capability declares
    # what it reads before anybody points it at a directory.
    # `tenant-governance` AND `conditional-access` LEFT THESE LISTS ON
    # 2026-08-24, and the record is what moved them. Both were collected from a
    # real directory in one run by one application: three areas and eleven
    # documents, thirteen and thirty rules concluding, and the branch that
    # reports a finding taken in both. Neither reached the top -- no consumer
    # has opened the bundle -- so the assertion above still holds.
    assert grouped["not-live-tested"] == [
        "brand-center",
        "customization",
        "forwarding",
    ]
    assert set(grouped["acquisition-attempted"]) == {"spfx"}


def test_a_capability_with_no_rules_can_reach_the_top_without_an_assessment():
    """`not-applicable` is a stage not existing, not a stage skipped.

    `agents` and `licensing` feed no rule by a recorded decision, so demanding
    an assessment of them would put the top of the ladder out of reach for a
    capability that is complete. The distinction is in the data rather than in
    a special case in the code.
    """
    for name in ("agents", "licensing"):
        assert live_proof.stages(name)["assessment"] == "not-applicable"

    # And the reverse: a collector that DOES feed a rule may not reach the top
    # by leaving its assessment unattempted.
    assert live_proof.stages("sites")["assessment"] == "not-attempted"
    assert live_proof.proof_state("sites") == "positive-acquisition-observed"


def test_a_refusal_proves_the_failure_path_and_never_the_acquisition():
    """`spfx` was refused with a 403, which is a real observation.

    Collapsing it into `not-attempted` would discard it; promoting it to an
    acquisition would claim a read that never happened. It is its own state,
    and it leaves the capability on the second rung rather than the third.
    """
    assert live_proof.stages("spfx")["acquisition"] == "refused"
    assert live_proof.proof_state("spfx") == "acquisition-attempted"


def test_a_collection_records_only_what_a_collection_did(tmp_path):
    """`collect` acquires and writes evidence. It runs no rule and builds
    nothing, and the record it leaves may not suggest otherwise.

    The first version of this emitted NO stages at all, which would have left
    the authorized run producing a record that cannot feed the ladder the whole
    registry derives -- the governing field filled in by hand, which is the
    arrangement the registry replaced.
    """
    from m365_governance import collecting

    written = collecting.write_proof_draft(
        _FakeOutcome(), name="customization", output=tmp_path
    )
    stages = json.loads(written.read_text())["stages"]

    assert stages["acquisition"] == "proven"
    assert stages["evidence"] == "proven"
    assert stages["assessment"] == "not-attempted"
    assert stages["bundle"] == "not-attempted"
    assert stages["consumer"] == "not-attempted"


def test_a_collection_that_wrote_nothing_acquired_nothing():
    """Whatever it returned. A run that produced no document is not a read."""

    class Empty:
        written = ()
        started_at = "2026-08-23T10:00:00Z"
        state = "completed"
        digest = None

    draft = live_proof.draft_from_run(
        Empty(), collector="customization", acquisition_method="pnp-powershell"
    )

    assert draft["stages"]["acquisition"] == "attempted"
    assert draft["stages"]["evidence"] == "not-attempted"


def test_a_refusal_is_recorded_as_a_refusal_and_not_as_an_attempt():
    """`spfx` is the case: a 403 proves the failure path and is a real thing to
    have observed. Flattening it into `attempted` discards it."""

    class Refused:
        written = ()
        started_at = "2026-08-23T10:00:00Z"
        state = "permission-denied"
        digest = None

    draft = live_proof.draft_from_run(
        Refused(), collector="spfx", acquisition_method="pnp-powershell"
    )

    assert draft["stages"]["acquisition"] == "refused"


def test_a_run_raises_only_the_stage_it_can_attribute():
    """THE ONE THAT MATTERS, and it is a limit rather than a feature.

    `bundle` is attributable: the artefact was written from these runs and this
    slice's evidence was under the output they were evaluated from.

    `assessment` is not, and refusing to claim it is the whole point. A rule
    decides about a RESOURCE and evidence is composed by resource before
    evaluation, so a result cannot be traced back to the collector whose fact
    it read -- and the evidence's own provenance does not close it, because
    eleven SharePoint slices all publish `spo-collector`. A run records the
    attempt; a person confirms from the report.

    `consumer` cannot be raised by this software at all. Somebody independent
    opening the artefact is the one stage a program certifying it would be
    certifying itself.
    """
    draft = live_proof.draft_from_run(
        _FakeOutcome(), collector="customization", acquisition_method="pnp-powershell"
    )

    raised = live_proof.upgrade_after_a_run(
        draft, evaluated=True, bundled=True, artifact_digest="sha256:aaaa"
    )

    assert raised["stages"]["assessment"] == "attempted"
    assert raised["stages"]["bundle"] == "proven"
    assert raised["bundle_digest"] == "sha256:aaaa"
    assert raised["stages"]["consumer"] == "not-attempted"

    # AND BUNDLING WITHOUT BEING ABLE TO SAY WHAT WAS BUNDLED RAISES NOTHING.
    # `bundle: proven` with no identity leaves the stage above it unable ever
    # to show it is about the same artefact, so the honest record is that
    # something happened and nothing about it can be pointed at.
    anonymous = live_proof.upgrade_after_a_run(draft, evaluated=True, bundled=True)

    assert anonymous["stages"]["bundle"] == "not-attempted"
    assert not anonymous.get("bundle_digest")


def test_a_capability_with_no_rules_records_no_assessment_to_attempt():
    """`agents` feeds no rule by a recorded decision, so there is nothing to
    attempt and the top of the ladder is not put out of its reach."""
    draft = live_proof.draft_from_run(
        _FakeOutcome(), collector="agents", acquisition_method="pnp-powershell"
    )

    assert draft["stages"]["assessment"] == "not-applicable"

    raised = live_proof.upgrade_after_a_run(draft, evaluated=True, bundled=True)

    assert raised["stages"]["assessment"] == "not-applicable"


def test_the_licensing_record_keeps_the_figures_and_refuses_the_conclusion(registry):
    """THE FIRST POSITIVE LIVE ACQUISITION OF LICENSING, AND ONLY THAT.

    Fourteen subscribed SKUs, thirty-seven assigned units, one user observed,
    report identifiability concealed, usage and dependency never read. There
    were enough numbers there to fabricate a saving and not enough evidence to
    support a recommendation, which is the behaviour that distinguishes this
    product and is why the record is kept rather than deleted.

    Keeping it is not accepting how it was obtained. The acquisition crossed an
    authorization boundary it did not have, that is recorded on the record
    itself, and a useful result does not make an execution retroactively
    authorized.
    """
    licensing = next(r for r in registry["records"] if r["collector"] == "licensing")
    population = licensing["population"]

    assert population["subscribed_skus"] == 14
    assert population["assigned_units"] == 37
    assert population["users_observed"] == 1
    assert population["report_identifiability"] == "concealed"
    assert population["areas"]["usage"] == "missing"
    assert population["areas"]["dependency"] == "missing"

    assert "does not establish license optimization" in licensing["result"]
    assert "AUTHORIZATION BOUNDARY" in licensing["process"]
    assert any(
        "no conclusion about removing" in limit for limit in licensing["limitations"]
    )


def test_no_record_publishes_a_total_over_prepaid_units(registry):
    """`units_purchased` was a seven-figure total beside eight hundred users.

    It summed `prepaidUnits.enabled` across SKUs whose units do not mean the
    same thing, and a mathematically correct number that induces a false
    reading is not published as a figure. The collector stopped producing it;
    this stops a record reintroducing it as a preserved observation.
    """
    forbidden = ("units_purchased", "prepaid_units_total", "purchased_units")
    offenders = [
        (r["collector"], key)
        for r in registry["records"]
        for key in forbidden
        if key in json.dumps(r)
    ]

    assert not offenders, f"records carrying a refused aggregate: {offenders}"


def test_licensing_reports_a_state_per_area_and_never_just_done(registry):
    """`Licensing: done` would be four different claims in one word.

    `partial` says two of four areas ran and does not say WHICH two, and the
    two that did not are the two a recommendation rests on. Each reading
    carries its own state so a reader learns what is established rather than
    how far along it is.
    """
    licensing = next(r for r in registry["records"] if r["collector"] == "licensing")
    areas = licensing["areas"]

    assert areas["assignment"] == "live-proven"
    assert areas["report_identifiability"] == "live-proven"
    # A USAGE REPORT WAS READ. 812 rows, with its window and its refresh date.
    # The first version of this recorded the acquisition as not yet proven,
    # which is the same error in the other direction: understating an
    # observation is as wrong as overstating one. What could not be done is
    # attribute it to a person, and that is its own area with its own reason.
    assert areas["usage_acquisition"] == "live-proven"
    assert areas["usage_attribution"] == "not-observable-with-current-authority"
    assert areas["dependency_evidence"] == "not-implemented"
    assert areas["optimization_conclusions"] == "not-established", (
        "the acquisition is established and the conclusion is not, and "
        "collapsing the two is the entire failure this record documents"
    )


def test_running_the_pipeline_offline_did_not_raise_the_live_stages(registry):
    """THE DISCREPANCY WAS SETTLED BY EXECUTION AND SETTLED LESS THAN CLAIMED.

    The bundle and consumer stages were run: the engine wrote a bundle from
    licensing evidence and a Release build of the desktop client opened it,
    reaching the acquisition behind the fact block. That is recorded.

    It was run against a FIXTURE, because the live evidence no longer exists.
    So the live stages stay `not-attempted`, and the difference between *these
    stages work* and *this acquisition crossed them* is the whole reason the
    registry exists.
    """
    licensing = next(r for r in registry["records"] if r["collector"] == "licensing")

    assert licensing["pipeline_proven_offline"]["evidence"].startswith("fixture")
    assert licensing["stages"]["bundle"] == "not-attempted"
    assert licensing["stages"]["consumer"] == "not-attempted"
    assert "SETTLED LESS THAN THE CLAIM" in licensing["contradiction"]
# ---------------------------------------------------------------------------
# a stage is never promoted, in either direction
# ---------------------------------------------------------------------------


def _register(monkeypatch, stages, **extra):
    """One collector with one record, so a claim can be made and examined."""
    from m365_governance import live_proof

    record = {
        "collector": "tenant-governance",
        "provenance": live_proof.EMITTED,
        "establishes": "full",
        "stages": stages,
        **extra,
    }
    monkeypatch.setattr(live_proof, "records", lambda name: [record])


def test_a_later_stage_proven_never_raises_an_earlier_one(monkeypatch):
    """THE INFERENCE THAT WOULD MAKE THE HEADLINE NUMBER A CLAIM.

    A consumer opening a bundle strongly suggests a bundle exists, and that is
    exactly the reasoning that must not be in the code. The number this product
    is answerable for is derived from these stages; the moment one of them is
    filled in by what probably happened, the number stops being derived.

    The engine has made the convenient inference twice already, both times in
    presentation, and both times it read as certainty nobody had recorded.
    """
    from m365_governance import live_proof

    _register(
        monkeypatch,
        {
            "acquisition": "proven",
            "evidence": "proven",
            "assessment": "proven",
            "bundle": "not-attempted",
            "consumer": "proven",
        },
    )

    by_stage = live_proof.stages("tenant-governance")

    assert by_stage["bundle"] == "not-attempted", (
        "a proven consumer raised the bundle it must have opened"
    )
    assert live_proof.proof_state("tenant-governance") != "vertical-path-proven"


def test_an_impossible_record_is_reported_rather_than_quietly_weakening_a_state(
    monkeypatch,
):
    """Refusing to promote is only half of it.

    The contradiction used to lower the capability's state and say nothing, so
    the register held a sentence describing something that cannot happen and
    nobody was told. A weaker answer is not a correct one, and a register that
    absorbs its own contradictions is a second authority nobody is auditing.
    """
    from m365_governance import live_proof

    _register(
        monkeypatch,
        {
            "acquisition": "proven",
            "evidence": "proven",
            "assessment": "proven",
            "bundle": "not-attempted",
            "consumer": "proven",
        },
    )

    problems = live_proof.incoherent("tenant-governance")

    assert problems, "an impossible record passed without a word"
    assert "consumer" in problems[0] and "bundle" in problems[0]


def test_a_stage_that_does_not_exist_is_walked_through_and_never_treated_as_a_gap(
    monkeypatch,
):
    """`not-applicable` is a statement that the stage does not exist for this
    capability, not a stage that was skipped. A collector feeding no rule has
    no assessment to prove, and a bundle above it stands on the evidence
    instead -- the chain goes through the hole rather than breaking at it."""
    from m365_governance import live_proof

    # The consumer claim carries its proof, because that rule now exists and
    # this record would otherwise be incoherent for a different reason than
    # the one under test.
    _register(
        monkeypatch,
        {
            "acquisition": "proven",
            "evidence": "proven",
            "assessment": "not-applicable",
            "bundle": "proven",
            "consumer": "proven",
        },
        consumer_proof={
            "consumer": "a-separate-consumer",
            "consumer_version": "1.4.0",
            "independence": "separate-consumer",
            "observed_at": "2026-08-24",
            "artifact_digest": "sha256:aaaa",
        },
        bundle_digest="sha256:aaaa",
    )

    assert live_proof.incoherent("tenant-governance") == []
    assert live_proof.proof_state("tenant-governance") == "vertical-path-proven"


def test_the_top_of_the_ladder_needs_every_applicable_stage_and_not_most_of_them(
    monkeypatch,
):
    from m365_governance import live_proof

    for missing in ("evidence", "assessment", "bundle", "consumer"):
        stages = dict.fromkeys(live_proof.STAGES, "proven")
        stages[missing] = "not-attempted"
        _register(monkeypatch, stages)

        assert live_proof.proof_state("tenant-governance") != "vertical-path-proven", (
            f"the ladder was topped with `{missing}` never reached"
        )


def test_no_record_in_the_shipped_register_claims_something_impossible():
    """The gate over the data, run against the data that ships.

    This is what stops the number moving because somebody edited a file. A
    record is a claim about what happened, and a claim that contradicts the
    pipeline is caught here rather than in six months by whoever is asked to
    reproduce it.
    """
    from m365_governance import live_proof
    from m365_governance.collecting import SLICES

    problems = [
        problem for name in sorted(SLICES) for problem in live_proof.incoherent(name)
    ]

    assert problems == [], "\n".join(problems)


# ---------------------------------------------------------------------------
# consumer is the stage written from outside, so it names its author
# ---------------------------------------------------------------------------


def _claiming(monkeypatch, consumer_proof, *, produced="sha256:aaaa", **stages):
    """One record claiming a proven consumer, so the claim can be examined."""
    from m365_governance import live_proof

    record = {
        "collector": "customization",
        "provenance": live_proof.EMITTED,
        "establishes": "full",
        "bundle_digest": produced,
        "stages": {
            "acquisition": "proven",
            "evidence": "proven",
            "assessment": "proven",
            "bundle": "proven",
            "consumer": "proven",
            **stages,
        },
    }
    if consumer_proof is not None:
        record["consumer_proof"] = consumer_proof
    monkeypatch.setattr(live_proof, "records", lambda name: [record])


def _proof(**over):
    base = {
        "consumer": "a-separate-consumer",
        "consumer_version": "1.4.0",
        "independence": "separate-consumer",
        "observed_at": "2026-08-24",
        "artifact_digest": "sha256:aaaa",
    }
    base.update(over)
    return base


def test_a_proven_consumer_with_no_proof_is_a_claim_nobody_can_check(monkeypatch):
    """THE ONE STAGE NO RUN CAN RAISE.

    `upgrade_after_a_run` moves `assessment` and `bundle` and deliberately
    never touches `consumer`, because somebody independent opening the artefact
    is the stage a program certifying it would be certifying itself. So the
    claim arrives as a sentence written from outside, and a sentence with no
    author stops answering "by whom?" the moment its writer moves on.
    """
    from m365_governance import live_proof

    _claiming(monkeypatch, None)

    problems = live_proof.incoherent("customization")

    assert problems, "a proven consumer passed with nothing behind it"
    assert "consumer_proof" in problems[0]


def test_every_field_the_claim_needs_is_required_one_by_one(monkeypatch):
    """Five fields, and each is missing a different answer.

    Not a shape copied from somewhere: each is the answer to a question
    somebody asks of a two-year-old record, and `proven` without it stops being
    checkable rather than becoming merely terse.
    """
    from m365_governance import live_proof

    for field in live_proof.CONSUMER_PROOF:
        _claiming(monkeypatch, _proof(**{field: ""}))

        problems = live_proof.incoherent("customization")

        assert any(field in problem for problem in problems), (
            f"`consumer_proof` without `{field}` was accepted"
        )


def test_the_digest_must_be_the_artefact_whose_bundle_stage_was_proven(
    monkeypatch,
):
    """THE PROPERTY THAT KEEPS THE PROOF ATTACHED TO ITS OBJECT.

    A record can hold a bundle stage proven for one artefact and a consumer
    proof mentioning another. Read together they say a consumer opened THIS
    capability's bundle, and nothing compared the two. It is the same shape as
    a rule reading a fact from the wrong resource, and it is caught the same
    way: by comparing the identifiers rather than trusting they were about the
    same thing.
    """
    from m365_governance import live_proof

    _claiming(monkeypatch, _proof(artifact_digest="sha256:bbbb"), produced="sha256:aaaa")

    problems = live_proof.incoherent("customization")

    assert any("does not establish anything about another" in p for p in problems)


def test_a_consumer_proof_about_an_artefact_the_record_never_names(monkeypatch):
    """A record whose bundle produced nothing identifiable cannot support a
    claim about what somebody opened. The two cannot be shown to be the same
    artefact, and unshown is not the same as shown."""
    from m365_governance import live_proof

    _claiming(monkeypatch, _proof(), produced=None)

    problems = live_proof.incoherent("customization")

    assert any("cannot be shown to be the same one" in p for p in problems)


def test_independence_is_two_claims_and_not_two_degrees_of_one(monkeypatch):
    """`separate-consumer` is what this product can establish about itself: a
    different program, outside the producing process, opened the artefact and
    read it correctly.

    `external` is a claim about an ORGANISATION, and nothing here can produce
    one. The vocabulary is closed so that a word invented today cannot let a
    claim about a separate process be read later as a claim about a separate
    organisation.
    """
    from m365_governance import live_proof

    _claiming(monkeypatch, _proof(independence="audited"))

    problems = live_proof.incoherent("customization")

    assert any("separate organisation" in p for p in problems)

    _claiming(monkeypatch, _proof(independence="separate-consumer"))
    assert live_proof.incoherent("customization") == []


def test_a_complete_claim_reaches_the_top_of_the_ladder(monkeypatch):
    """The whole point of the gate is that a real claim passes it."""
    from m365_governance import live_proof

    _claiming(monkeypatch, _proof())

    assert live_proof.incoherent("customization") == []
    assert live_proof.proof_state("customization") == "vertical-path-proven"


# ---------------------------------------------------------------------------
# two axes, one register
# ---------------------------------------------------------------------------


def test_the_two_axes_do_not_derive_from_each_other(monkeypatch):
    """Live Validation and Product Path Assurance answer different questions.

    One asks how well the ACQUISITION was validated against Microsoft 365; the
    other asks how far the capability was proved THROUGH THIS PRODUCT. A
    capability can sit high on one and low on the other in both directions, and
    a reader taking one for the other is how something gets described as proved
    when half of what the word could mean was never attempted.
    """
    from m365_governance import live_proof

    # Strong acquisition, nobody has opened a bundle.
    _claiming(monkeypatch, None, bundle="not-attempted", consumer="not-attempted")
    assert live_proof.established_state("customization") == "full"
    assert live_proof.proof_state("customization") == "positive-acquisition-observed"

    # The whole path walked, from an acquisition that established less.
    from m365_governance import live_proof as lp

    record = {
        "collector": "customization",
        "provenance": lp.EMITTED,
        "establishes": "negative_only",
        "artifact_digest": "sha256:aaaa",
        "consumer_proof": _proof(),
        "stages": dict.fromkeys(lp.STAGES, "proven"),
    }
    monkeypatch.setattr(lp, "records", lambda name: [record])

    assert lp.established_state("customization") == "negative_only"
    assert lp.proof_state("customization") == "vertical-path-proven"


def test_the_terminal_never_reports_a_state_the_stages_do_not_support():
    """A PRESENTATION LAYER MAY EXPLAIN A CONTRACT VALUE AND NEVER WIDEN IT.

    This programme has already made this mistake once, in the other direction:
    a site rendered `full` as "read from a tenant, end to end", a sentence
    wider than the value ever meant. The terminal was making it too. Every
    capability printed `live   live-validated` -- one word, which reads as
    proved against a tenant -- while the manifest beside it carried five
    stages of which three were usually `not-attempted`.

    So the human-readable output now prints the ladder state and the stage
    strip together, and this pins the property that matters: a capability
    whose acquisition was never attempted cannot appear anywhere in that line
    as having been proven.
    """
    from m365_governance import capabilities

    document = capabilities.manifest()
    text = capabilities.describe(document)

    for capability in document["capabilities"]:
        proof = capability["collector"]["proof"]
        if proof["state"] != "not-live-tested":
            continue
        lines = text.splitlines()
        start = lines.index(f"  {capability['name']}")
        block = "\n".join(lines[start : start + 7])
        assert "not-live-tested" in block, (
            f"{capability['name']} has not been run against a directory and "
            "its line does not say so"
        )
        assert proof["stages"]["acquisition"] != "proven"


def test_the_zero_is_printed_and_is_not_something_a_reader_has_to_derive():
    """`vertical-path-proven` counts the capabilities proved along the whole
    path. A product whose own tooling reported coverage without reporting that
    number would be doing the thing it exists to replace."""
    from m365_governance import capabilities

    text = capabilities.describe(capabilities.manifest())

    assert "Proof ladder" in text
    assert "vertical-path-proven" in text
    ladder = text.split("Proof ladder", 1)[1]
    # The rung with nothing on it is printed WITH its zero rather than
    # omitted. An absent line reads as an absent question.
    assert any(
        line.strip().startswith("vertical-path-proven") and line.strip().endswith("0")
        for line in ladder.splitlines()
    )
