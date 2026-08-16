"""The account a collection writes of itself, beside the evidence it produced.

THE MANIFEST DESCRIBES THE COLLECTION; THE DOCUMENTS DESCRIBE EVIDENCE. Every
test here holds that line. A state that lived inside each evidence document
would be one truth written once per document, and it could not answer the case
the whole contract exists for: a collection that stopped halfway has to say
what it did not read, and the documents that would have carried that sentence
are exactly the ones that were never written.

Nothing here reaches a tenant. The manifest is built from an `Outcome` and from
artefacts on disk, which is where every decision in it is made.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from m365_governance import canonical, registry
from m365_governance.collecting import (
    DIGESTED,
    MANIFEST,
    Outcome,
    State,
    build_manifest,
    incomplete_coverage,
    manifests,
    write_manifest,
)
from m365_governance.resources import packaged

CONTRACT = "https://ph7x.com/schemas/m365-governance/collection/1.0.0"

#: Built once. The registry is what makes a cross-document `$ref` resolve
#: without going near a network: the collection references the evidence's own
#: `tenant` and `coverage` definitions, so one definition moves at a time.
SCHEMAS = registry.SchemaRegistry.load(packaged("schemas"))


def problems(document: dict) -> list[str]:
    """Against the contract the document itself declares, never the newest."""
    return SCHEMAS.problems(document)


def _outcome(**kwargs) -> Outcome:
    base = {
        "slice_name": "sites",
        "returncode": 0,
        "seconds": 1.5,
        "written": [],
        "stdout": "",
        "stderr": "",
        "started_at": "2026-08-16T09:00:00Z",
        "finished_at": "2026-08-16T09:00:02Z",
    }
    return Outcome(**{**base, **kwargs})


def _evidence(
    path: Path,
    requested: list[str],
    completed: list[str],
    unavailable: dict | None = None,
    *,
    identity_kind: str = "delegated",
    host: str = "contoso.sharepoint.com",
    collector_version: str = "1.4.0",
) -> Path:
    path.write_text(
        json.dumps(
            {
                "provenance": {
                    "identity_kind": identity_kind,
                    "collector_version": collector_version,
                    "tenant": {"id": None, "host": host},
                },
                "coverage": {
                    "requested": requested,
                    "completed": completed,
                    "unavailable": unavailable or {},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _built(outcome: Outcome, directory: Path, **kwargs) -> dict:
    settings = {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "site_url": None,
        "tenant_url": "https://contoso-admin.sharepoint.com",
        "device_login": False,
    }
    return build_manifest(outcome, directory=directory, **{**settings, **kwargs})


# ---------------------------------------------------------------------------
# it is a document of the contract it claims
# ---------------------------------------------------------------------------


def test_the_manifest_validates_against_the_contract_it_declares(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    manifest = _built(outcome, tmp_path)

    assert manifest["$schema"] == CONTRACT == registry.contract("collection")
    assert problems(manifest) == []


@pytest.mark.parametrize(
    "case",
    [
        "completed",
        "partial-clean",
        "partial-died",
        "failed",
        "cancelled",
    ],
)
def test_every_state_produces_a_document_of_the_contract(tmp_path, case):
    """Including the failure, which is the one nothing else records.

    A collection that produced no artefact is precisely the case a consumer
    cannot reconstruct from a directory, and a contract that only validated the
    happy path would leave it to be inferred from emptiness.
    """
    directory = tmp_path / case
    directory.mkdir()
    written = []
    returncode, cancelled = 0, False

    if case == "completed":
        written = [_evidence(directory / "a.json", ["sites"], ["sites"])]
    elif case == "partial-clean":
        written = [
            _evidence(
                directory / "a.json",
                ["sites", "owners"],
                ["sites"],
                {"owners": {"state": "permission-denied", "detail": "not an admin"}},
            )
        ]
    elif case == "partial-died":
        written = [_evidence(directory / "a.json", ["sites"], ["sites"])]
        returncode = 1
    elif case == "failed":
        returncode = 1
    elif case == "cancelled":
        written = [_evidence(directory / "a.json", ["sites"], ["sites"])]
        returncode, cancelled = 130, True

    outcome = _outcome(
        written=written,
        returncode=returncode,
        cancelled=cancelled,
        incomplete=incomplete_coverage(written),
    )
    manifest = _built(outcome, directory)

    assert problems(manifest) == []
    assert manifest["state"] == str(outcome.state)


def test_a_failed_collection_still_writes_an_account_of_itself(tmp_path):
    directory = tmp_path / "never-created"
    outcome = _outcome(returncode=1)

    path = write_manifest(
        outcome,
        directory=directory,
        client_id="a-client",
        site_url=None,
        tenant_url="https://contoso-admin.sharepoint.com",
        device_login=False,
    )

    assert path is not None and path.is_file()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert manifest["artefacts"] == []
    assert problems(manifest) == []


# ---------------------------------------------------------------------------
# nothing in it is inferred from the exit code
# ---------------------------------------------------------------------------


def test_the_tenant_the_identity_and_the_collector_are_read_from_the_artefacts(
    tmp_path,
):
    doc = _evidence(
        tmp_path / "a.json",
        ["sites"],
        ["sites"],
        identity_kind="application",
        host="fabrikam.sharepoint.com",
        collector_version="2.1.0",
    )
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    manifest = _built(outcome, tmp_path)

    assert manifest["observed"] == {"id": None, "host": "fabrikam.sharepoint.com"}
    assert manifest["identity"]["kind"] == "application"
    assert manifest["versions"]["collector"] == "2.1.0"


def test_nothing_written_means_nobody_read_it_rather_than_a_guess(tmp_path):
    """The three facts above are absent, and say so, on a collection that failed."""
    manifest = _built(_outcome(returncode=1), tmp_path)

    assert manifest["observed"] is None
    assert manifest["identity"]["kind"] == "not-established"
    assert manifest["versions"]["collector"] is None
    # And the half that survives a total failure: what was asked for.
    assert manifest["requested"]["tenant_url"] == (
        "https://contoso-admin.sharepoint.com"
    )


def test_the_exit_code_is_published_raw_and_is_not_the_verdict(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(
        written=[doc], returncode=1, incomplete=incomplete_coverage([doc])
    )

    manifest = _built(outcome, tmp_path)

    assert manifest["exit_code"] == 1
    assert manifest["state"] == "partial"


def test_a_verdict_always_carries_the_facts_behind_it(tmp_path):
    doc = _evidence(
        tmp_path / "a.json",
        ["sites", "owners"],
        ["sites"],
        {"owners": {"state": "permission-denied", "detail": "not a site admin"}},
    )
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    because = _built(outcome, tmp_path)["because"]

    assert because
    assert any("owners not read" in reason for reason in because)


# ---------------------------------------------------------------------------
# coverage is a union of what the documents said, and never a count
# ---------------------------------------------------------------------------


def test_an_area_one_document_could_not_read_is_not_completed(tmp_path):
    """The rounding-up the states exist to stop, at collection level.

    One artefact read `owners` and another could not. The collection did not
    get all of `owners`, and a union that took `completed` as the union of both
    would report that it did.
    """
    first = _evidence(tmp_path / "a.json", ["sites", "owners"], ["sites", "owners"])
    second = _evidence(
        tmp_path / "b.json",
        ["sites", "owners"],
        ["sites"],
        {"owners": {"state": "permission-denied", "detail": "not a site admin"}},
    )
    written = [first, second]
    outcome = _outcome(written=written, incomplete=incomplete_coverage(written))

    coverage = _built(outcome, tmp_path)["coverage"]

    assert coverage["requested"] == ["owners", "sites"]
    assert coverage["completed"] == ["sites"]
    assert coverage["unavailable"]["owners"]["state"] == "permission-denied"


def test_coverage_carries_names_and_no_totals(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    coverage = _built(outcome, tmp_path)["coverage"]

    assert set(coverage) == {"requested", "completed", "unavailable"}
    assert all(isinstance(value, str) for value in coverage["requested"])


# ---------------------------------------------------------------------------
# the artefacts, named and digested, and never restated
# ---------------------------------------------------------------------------


def test_each_artefact_is_named_relative_to_the_manifest_and_digested(tmp_path):
    nested = tmp_path / "sub"
    nested.mkdir()
    doc = _evidence(nested / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    artefact = _built(outcome, tmp_path)["artefacts"][0]

    assert artefact["path"] == "sub/a.json"
    assert artefact["digest"] == hashlib.sha256(doc.read_bytes()).hexdigest()
    assert artefact["bytes"] == len(doc.read_bytes())
    assert artefact["readable"] is True


def test_the_manifest_does_not_restate_what_a_document_says_about_a_resource(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    artefact = _built(outcome, tmp_path)["artefacts"][0]

    assert set(artefact) == {"path", "digest", "bytes", "readable"}


def test_an_unreadable_artefact_is_a_reason_to_doubt_and_not_a_file_to_skip(tmp_path):
    broken = tmp_path / "a.json"
    broken.write_text("{ not json", encoding="utf-8")
    outcome = _outcome(written=[broken], incomplete=incomplete_coverage([broken]))

    manifest = _built(outcome, tmp_path)

    assert manifest["artefacts"][0]["readable"] is False
    assert any("could not be read back" in r for r in manifest["because"])
    assert manifest["state"] == "partial"


# ---------------------------------------------------------------------------
# the digest, and the identity that derives from it
# ---------------------------------------------------------------------------


def test_the_identity_is_the_digest_and_a_recipient_can_recompute_it(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    manifest = _built(outcome, tmp_path)

    recomputed = canonical.digest(
        {k: manifest[k] for k in manifest["digest"]["covers"]}
    )
    assert manifest["digest"]["value"] == recomputed
    assert manifest["collection_id"] == recomputed


def test_the_digest_names_what_it_covers_rather_than_leaving_it_to_be_known(tmp_path):
    manifest = _built(_outcome(returncode=1), tmp_path)

    assert manifest["digest"]["covers"] == list(DIGESTED)
    # The identity and the block holding it are the two members left out: a
    # digest that covered its own value could never be computed.
    assert "collection_id" not in manifest["digest"]["covers"]
    assert "digest" not in manifest["digest"]["covers"]


def test_a_document_edited_after_the_fact_no_longer_matches_its_digest(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites", "owners"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))
    manifest = _built(outcome, tmp_path)

    manifest["state"] = "completed"

    recomputed = canonical.digest(
        {k: manifest[k] for k in manifest["digest"]["covers"]}
    )
    assert recomputed != manifest["digest"]["value"]


# ---------------------------------------------------------------------------
# two collections in one directory, and the record that is never destroyed
# ---------------------------------------------------------------------------


def _write(outcome: Outcome, directory: Path, **kwargs) -> Path:
    settings = {
        "client_id": "a-client",
        "site_url": None,
        "tenant_url": "https://contoso-admin.sharepoint.com",
        "device_login": False,
    }
    path = write_manifest(outcome, directory=directory, **{**settings, **kwargs})
    assert path is not None
    return path


def test_the_first_collection_takes_the_plain_name(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    assert _write(outcome, tmp_path).name == MANIFEST


def test_a_second_collection_never_replaces_the_first_ones_account(tmp_path):
    """The defect this naming rule exists to prevent.

    Overwriting would destroy the only record that the earlier collection was
    partial, and nothing would be left to say so: the evidence it wrote is
    still there, and evidence describes a resource rather than a batch.
    """
    partial = _evidence(tmp_path / "a.json", ["sites", "owners"], ["sites"])
    first = _write(
        _outcome(written=[partial], incomplete=incomplete_coverage([partial])), tmp_path
    )
    assert json.loads(first.read_text(encoding="utf-8"))["state"] == "partial"

    clean = _evidence(tmp_path / "b.json", ["owners"], ["owners"])
    second = _write(
        _outcome(
            written=[clean],
            incomplete=incomplete_coverage([clean]),
            started_at="2026-08-16T10:00:00Z",
        ),
        tmp_path,
    )

    assert second != first
    assert json.loads(first.read_text(encoding="utf-8"))["state"] == "partial"
    assert json.loads(second.read_text(encoding="utf-8"))["state"] == "completed"
    assert {m["state"] for m in manifests(tmp_path)} == {"partial", "completed"}


def test_the_same_collection_written_twice_stays_one_file(tmp_path):
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    assert _write(outcome, tmp_path) == _write(outcome, tmp_path)
    assert len(manifests(tmp_path)) == 1


# ---------------------------------------------------------------------------
# what a consumer reads, and what it must not conclude from silence
# ---------------------------------------------------------------------------


def test_evidence_with_no_manifest_makes_no_claim_about_completeness(tmp_path):
    """Legacy evidence, and evidence exported from elsewhere.

    An empty list here means nobody said. It must never be read as everything
    having been collected, which is why the caller is given nothing to round up.
    """
    _evidence(tmp_path / "a.json", ["sites"], ["sites"])

    assert manifests(tmp_path) == []


def test_a_manifest_is_not_evidence_and_is_not_collected_as_one(tmp_path):
    """Both directions of one mistake.

    `_files` must not count a manifest as a document the collector wrote, and
    `_evidence_documents` must not hand one to the evaluator. A `.json` file
    sitting among evidence is not evidence because of where it lives.
    """
    from m365_governance.cli import _evidence_documents
    from m365_governance.collecting import _files

    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    _write(_outcome(written=[doc], incomplete=incomplete_coverage([doc])), tmp_path)

    assert _files(tmp_path) == [doc]
    assert _evidence_documents(tmp_path) == [doc]


# ---------------------------------------------------------------------------
# the whole path, from the command that collects to the command that evaluates
# ---------------------------------------------------------------------------


def test_collect_writes_the_manifest_beside_the_evidence(tmp_path, monkeypatch):
    """`run_slice` end to end, with the process itself stood in for.

    The process is exercised elsewhere against a real child. What is under test
    here is the wiring: a collection that ends produces an account of itself
    without anybody asking for one, and the outcome says where it is.
    """
    from m365_governance import collecting

    def collector(argv, on_progress):
        _evidence(tmp_path / "site.json", ["sites", "owners"], ["sites"])
        if on_progress is not None:
            on_progress("  1 site enumerated by this identity")
        return 0, "  1 site enumerated by this identity", "", False

    monkeypatch.setattr(collecting, "_run", collector)

    outcome = collecting.run_slice(
        "sites",
        client_id="00000000-0000-0000-0000-000000000000",
        output=tmp_path,
        tenant_url="https://contoso-admin.sharepoint.com",
    )

    assert outcome.state is State.PARTIAL
    assert outcome.manifest_path == tmp_path / MANIFEST

    manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
    assert problems(manifest) == []
    assert manifest["state"] == "partial"
    assert manifest["slice"] == {
        "name": "sites",
        "mode": "TenantSites",
        "describes": "every site this identity can enumerate",
        "profile": "capacity",
    }
    assert [a["path"] for a in manifest["artefacts"]] == ["site.json"]
    assert manifest["started_at"] and manifest["finished_at"]


def _real_evidence(target: Path) -> Path:
    """A packaged fixture, because the evaluator validates what it is given."""
    source = packaged("fixtures") / "sharepoint" / "site-storage-comfortable.json"
    target.write_bytes(source.read_bytes())
    return target


def test_evaluate_states_the_bound_before_the_results(tmp_path, capsys):
    """What was read bounds everything that follows, so it is printed first.

    On stderr, so a pipeline reading JSON on stdout is unaffected: the bound is
    for the person, and the document is for the program.
    """
    from m365_governance.cli import main

    doc = _real_evidence(tmp_path / "site.json")
    _write(
        _outcome(
            written=[doc],
            incomplete=["site.json: owners not read (owners: permission-denied)"],
        ),
        tmp_path,
    )

    assert main(["evaluate", "--evidence", str(tmp_path), "--format", "json"]) == 0

    captured = capsys.readouterr()
    assert "1 collections produced this evidence, 1 of them incomplete" in captured.err
    assert "owners not read" in captured.err
    # And it still evaluated: a partial collection is evidence, not a refusal.
    assert json.loads(captured.out)


def test_evaluate_claims_nothing_about_evidence_that_carries_no_manifest(
    tmp_path, capsys
):
    """Legacy evidence, and evidence exported from somewhere else.

    Silence here is the correct answer. Saying "complete" would be the engine
    reporting a gap it never measured as an absence of gaps.
    """
    from m365_governance.cli import main

    _real_evidence(tmp_path / "site.json")

    assert main(["evaluate", "--evidence", str(tmp_path), "--format", "json"]) == 0

    captured = capsys.readouterr()
    assert "collections produced this evidence" not in captured.err
    assert json.loads(captured.out)


# ---------------------------------------------------------------------------
# the awkward paths, which are the ones a collection actually takes
# ---------------------------------------------------------------------------


def test_a_manifest_can_be_named_directly_rather_than_found(tmp_path):
    """A consumer holding one file, not a directory. Both are ordinary."""
    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    path = _write(
        _outcome(written=[doc], incomplete=incomplete_coverage([doc])), tmp_path
    )

    assert [m["state"] for m in manifests(path)] == ["completed"]
    # And a path that is neither is not an error, because absence is an answer.
    assert manifests(tmp_path / "nothing-here") == []


def test_a_manifest_that_cannot_be_read_is_not_an_account_and_stops_nothing(tmp_path):
    """It must not become a claim, and it must not refuse an evaluation.

    A file the engine cannot parse says nothing about how much of a tenant was
    read. Treating it as complete would invent an answer; raising would let a
    damaged sidecar block evidence that is perfectly good.
    """
    (tmp_path / MANIFEST).write_text("{ truncated", encoding="utf-8")

    assert manifests(tmp_path) == []

    doc = _evidence(tmp_path / "a.json", ["sites"], ["sites"])
    second = _write(
        _outcome(written=[doc], incomplete=incomplete_coverage([doc])), tmp_path
    )
    # Unreadable, so it cannot be established as the same collection, and the
    # rule holds: what is already there is never replaced.
    assert second.name != MANIFEST


def test_an_artefact_outside_the_directory_keeps_its_own_path(tmp_path):
    """`--output` a file, and a manifest that sits beside it.

    A relative path would be a `..` chain that stops resolving the moment
    either end moves, so the truthful answer is the path itself.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    doc = _evidence(elsewhere / "a.json", ["sites"], ["sites"])
    outcome = _outcome(written=[doc], incomplete=incomplete_coverage([doc]))

    artefact = _built(outcome, tmp_path / "here")["artefacts"][0]

    assert artefact["path"] == str(doc)


def test_the_manifest_goes_beside_a_single_file_output(tmp_path):
    from m365_governance.collecting import _collection_directory

    assert _collection_directory(tmp_path / "sub" / "a.json") == tmp_path / "sub"
    # A path that does not exist and has no suffix is a directory nobody has
    # created yet, which is what a collection that failed immediately leaves.
    assert _collection_directory(tmp_path / "sub") == tmp_path / "sub"
    assert _collection_directory(tmp_path) == tmp_path


def test_an_engine_with_no_published_bundle_says_so_rather_than_inventing(
    tmp_path, monkeypatch
):
    """The bundle is generated and committed, and an installation may lack it.

    A version invented here would travel into every manifest that engine wrote
    and a consumer would compare it against a bundle that never existed.
    """
    from m365_governance import collecting

    monkeypatch.setattr(collecting, "packaged", lambda _name: tmp_path)

    assert collecting._contract_version() == "not-published"
