"""The evidence coverage matrix, and the rules that keep it honest.

The matrix exists because a catalogue of what was written reads, to a person
who does not already know, as a map of Microsoft 365. Ten SharePoint
capabilities and no mention of Exchange is a true list and a false picture.
These tests hold the three properties that make it a picture: nothing is
missing, nothing is typed that should be derived, and nothing enters supported.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from m365_governance import capabilities, collecting, domains


@pytest.fixture(scope="module")
def matrix() -> dict[str, dict]:
    return {entry["name"]: entry for entry in capabilities.manifest()["domains"]}


def test_every_slice_belongs_to_a_declared_domain():
    """A slice whose domain nobody declared would vanish from the matrix.

    It would still appear under `capabilities`, which is exactly the failure
    that is hard to see: the collector works, its tests pass, and the only
    thing wrong is that the map of Microsoft 365 stopped mentioning it.
    """
    undeclared = sorted(
        {s.domain for s in collecting.SLICES.values()} - set(domains.BY_KEY)
    )
    assert not undeclared, f"slices name domains nothing declares: {undeclared}"


def test_every_capability_appears_on_the_matrix_exactly_once(matrix):
    placed = [s["name"] for entry in matrix.values() for s in entry["surfaces"]]
    assert sorted(placed) == sorted(collecting.SLICES)
    assert len(placed) == len(set(placed))


def test_a_domain_nobody_collects_says_so_rather_than_being_absent(matrix):
    """THE ENTRIES THAT MAKE THIS DOCUMENT TRUE.

    Every domain with no acquisition surface has to be published, with the
    question it does not answer. Dropping them would leave a catalogue that is
    accurate about everything it mentions and wrong about Microsoft 365.
    """
    empty = [e for e in matrix.values() if not e["surfaces"]]
    assert empty, "the matrix lists only domains that are collected"
    for entry in empty:
        assert entry["state"] == domains.NOT_STARTED
        assert entry["question"].strip()
        assert entry["acquisition"].strip()
        assert "weakest_surface_state" not in entry


def test_a_domain_that_is_collected_carries_no_state_of_its_own(matrix):
    """`not-started` is the ONLY state a domain has in its own right.

    Anything else would be an aggregate over unlike observations, which `D5`
    refuses: a domain holding one proven surface and one unproven one is not
    half-proven. What it publishes instead is the state of its least proved
    surface, and a count per state.
    """
    for entry in matrix.values():
        if entry["surfaces"]:
            assert "state" not in entry, (
                f"{entry['name']} carries a state of its own. A domain's "
                "coverage is the facts it is made of, never a grade over them."
            )
            assert sum(entry["surfaces_by_state"].values()) == len(entry["surfaces"])


def test_the_weakest_surface_state_is_a_state_a_surface_actually_has(matrix):
    for entry in matrix.values():
        if not entry["surfaces"]:
            continue
        held = {s["live_validation_state"] for s in entry["surfaces"]}
        assert entry["weakest_surface_state"] in held


def test_no_domain_enters_supported(matrix):
    """The entry rule, as something that fails rather than something written.

    A domain arrives with no surface, gains one at `none`, and moves through
    `provider-only`, `partial` and `full` as live proof arrives. There is no
    field anywhere that says a domain is supported, and the reason this test
    exists is that the same inflation happened three times on single slices:
    `spfx` published `live-validated` for a branch no real catalog produced,
    `licensing` was one commit from publishing a state that was false, and
    `conditional-access` counted a transport read as a slice read.
    """
    banned = {"supported", "ready", "complete", "ga", "stable"}
    for entry in matrix.values():
        values = {str(v).lower() for v in entry.values() if isinstance(v, str)}
        assert not (values & banned), f"{entry['name']} declares a support level"

    # And the states themselves come from the contract, not from this matrix.
    allowed = {str(member.name).lower().replace("_", "-") for member in collecting.Live}
    for entry in matrix.values():
        for surface in entry["surfaces"]:
            assert surface["live_validation_state"] in allowed


def test_a_surface_state_is_the_one_its_capability_publishes(matrix):
    """Two projections of one fact, and no second place to keep it true."""
    published = {
        c["name"]: c["collector"]["live_validation_state"]
        for c in capabilities.manifest()["capabilities"]
    }
    for entry in matrix.values():
        for surface in entry["surfaces"]:
            assert surface["live_validation_state"] == published[surface["name"]]


def test_the_matrix_reaches_a_consumer_through_the_published_command():
    """It is only a contract if the command a consumer runs emits it."""
    argv = [sys.executable, "-m", "m365_governance.cli", "capabilities"]
    result = subprocess.run(
        [*argv, "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    document = json.loads(result.stdout)
    assert document["$schema"].endswith("/capability-manifest/1.2.0")
    assert len(document["domains"]) == len(domains.DOMAINS)
