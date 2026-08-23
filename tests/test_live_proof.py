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
