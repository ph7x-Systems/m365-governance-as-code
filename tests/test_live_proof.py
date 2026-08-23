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

    written = collecting._write_proof_draft(
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

    written = collecting._write_proof_draft(
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
    assert grouped["not-live-tested"] == ["customization"]
    assert set(grouped["acquisition-attempted"]) == {"conditional-access", "spfx"}


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

    written = collecting._write_proof_draft(
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

    raised = live_proof.upgrade_after_a_run(draft, evaluated=True, bundled=True)

    assert raised["stages"]["assessment"] == "attempted"
    assert raised["stages"]["bundle"] == "proven"
    assert raised["stages"]["consumer"] == "not-attempted"


def test_a_capability_with_no_rules_records_no_assessment_to_attempt():
    """`agents` feeds no rule by a recorded decision, so there is nothing to
    attempt and the top of the ladder is not put out of its reach."""
    draft = live_proof.draft_from_run(
        _FakeOutcome(), collector="agents", acquisition_method="pnp-powershell"
    )

    assert draft["stages"]["assessment"] == "not-applicable"

    raised = live_proof.upgrade_after_a_run(draft, evaluated=True, bundled=True)

    assert raised["stages"]["assessment"] == "not-applicable"
