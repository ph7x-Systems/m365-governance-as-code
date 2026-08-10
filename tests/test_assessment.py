"""An assessment carries what produced it, and proves it did not move.

`build` assembles one; `verify` checks one that arrived. They are separate on
purpose: verifying is what a consumer does to something somebody else made,
and it must not need the code that made it.
"""

from __future__ import annotations

import json

import pytest

from conftest import DATA
from m365_governance import assessment
from m365_governance.engine import evaluate
from m365_governance.loader import load_rules
from m365_governance.registry import SchemaRegistry
from m365_governance.results import RunSet

FIXTURES = DATA / "fixtures" / "sharepoint"
SCHEMAS = DATA / "schemas"
SAMPLE = DATA / "fixtures" / "assessment" / "three-resources.json"


def rules() -> list[dict]:
    return [loaded.data for loaded in load_rules(DATA / "rules")]


def built(**overrides) -> dict:
    names = overrides.pop(
        "names", ["site-agents-with-sources", "site-spfx-current", "list-class-content"]
    )
    documents = [json.loads((FIXTURES / f"{n}.json").read_text()) for n in names]
    runs = [evaluate(rules(), document) for document in documents]
    return assessment.build(
        RunSet(runs),
        documents,
        engine_version=overrides.pop("engine_version", "0.3.0"),
        created_at=overrides.pop("created_at", "2026-08-08T18:00:00Z"),
        **overrides,
    )


def contracts() -> SchemaRegistry:
    return SchemaRegistry.load(SCHEMAS)


def test_the_committed_sample_matches_its_schema():
    problems = contracts().problems(json.loads(SAMPLE.read_text()))
    assert not problems, problems[0]


def test_what_the_engine_builds_matches_its_schema():
    problems = contracts().problems(built())
    assert not problems, problems[0]


def test_the_identity_is_derived_and_not_assigned():
    """Two builds of the same inputs are the same assessment.

    An id somebody chose would let two different assessments claim to be one,
    and two exports of the same one disagree.
    """
    first, second = built(), built()
    identifier = first["canonical"]["manifest"]["assessment_id"]
    assert identifier == second["canonical"]["manifest"]["assessment_id"]
    assert identifier == first["canonical"]["hashes"]["canonical_hash"]


def test_a_different_evaluation_is_a_different_assessment():
    other = built(names=["site-spfx-current", "list-class-content"])
    assert (
        built()["canonical"]["manifest"]["assessment_id"]
        != other["canonical"]["manifest"]["assessment_id"]
    )


def test_the_manifest_is_covered_except_for_what_cannot_be():
    """`tenant`, `created_at` and the identity summary are facts about what was
    assessed, so changing one has to be detectable. An earlier version left the
    whole manifest out of the digests and a workspace test found the hole: an
    assessment could be relabelled as belonging to a different tenant and still
    verify."""
    assert "manifest" in built()["canonical"]["hashes"]["canonical_parts"]

    moves = (
        ("tenant", {"id": None, "host": "somebody-elses.sharepoint.com"}, True),
        ("created_at", "2020-01-01T00:00:00Z", True),
        ("identity", {"summary": "single", "kinds": ["application"]}, True),
        ("acquisition", {"summary": "single", "kinds": ["imported"]}, True),
        # A label is what a person calls it. Renaming is not producing a
        # different thing, so it is outside the digest and outside identity.
        ("label", "A better name", False),
    )
    for field, value, expected in moves:
        document = built(label="Original")
        document["canonical"]["manifest"][field] = value
        caught = any("manifest" in problem for problem in assessment.verify(document))
        assert caught is expected, f"changing {field} to {value!r}: caught={caught}"


def test_a_label_never_changes_the_identity():
    """What somebody calls it is not what it is, so it is left out of the
    digest alongside the id. Including it would give the same evaluation a new
    identity because somebody typed a better name, and every earlier reference
    would stop resolving."""
    assert (
        built()["canonical"]["manifest"]["assessment_id"]
        == built(label="Anything at all")["canonical"]["manifest"]["assessment_id"]
    )


def test_verify_accepts_what_build_produced():
    assert assessment.verify(built()) == []


@pytest.mark.parametrize(
    "part", ["run_set", "evidence", "versions"], ids=lambda p: f"tampered {p}"
)
def test_verify_catches_a_canonical_part_that_moved(part):
    """The whole reason the digests exist: something changed after the fact."""
    document = built()
    document["canonical"][part] = {"tampered": True}
    problems = assessment.verify(document)
    assert any(part in problem for problem in problems), problems


def test_verify_catches_an_id_that_was_assigned_rather_than_derived():
    document = built()
    document["canonical"]["manifest"]["assessment_id"] = "something-somebody-chose"
    assert any("derived" in problem for problem in assessment.verify(document))


def test_the_versions_come_from_what_was_evaluated():
    """Not from what is installed now. Two releases later, `the rule changed`
    has to be answerable, and only the run knows which version answered."""
    versions = built()["canonical"]["versions"]
    assert versions["rules"], "no rule versions were recorded"
    assert all(version for version in versions["rules"].values())
    assert versions["collectors"], "no collector versions were recorded"


def test_the_evidence_is_kept_whole():
    """A finding whose evidence was discarded cannot be re-checked."""
    document = built()
    assert len(document["canonical"]["evidence"]) == 3
    assert all("facts" in evidence for evidence in document["canonical"]["evidence"])


def test_a_multi_geo_host_is_never_silently_folded_into_the_primary():
    """One tenant reached at two hosts and no directory identity anywhere. The
    prefix looks shared and that is not evidence of anything: folding them
    would invent an identity nobody read, so it refuses and says what would
    settle it."""
    run_set, documents = one("site-spfx-current")
    satellite = json.loads((FIXTURES / "site-modern-clean.json").read_text())
    satellite["provenance"]["tenant"]["host"] = "contoso-emea.sharepoint.com"

    with pytest.raises(assessment.Mismatch, match="directory identity"):
        assessment.build(
            RunSet(run_set.runs + [evaluate(rules(), satellite)]),
            documents + [satellite],
            engine_version="0.3.0",
            created_at="2026-08-08T18:00:00Z",
        )


def test_the_directory_identity_settles_what_hosts_cannot():
    """Two addresses of one organisation, and something read the identity. The
    id is canonical, so this is one tenant and the hosts are endpoints."""
    run_set, documents = one("site-spfx-current")
    satellite = json.loads((FIXTURES / "site-modern-clean.json").read_text())
    satellite["provenance"]["tenant"]["host"] = "contoso-emea.sharepoint.com"
    directory = "9a1f0c7e-0000-4000-8000-00000000dead"
    for document in documents + [satellite]:
        document["provenance"]["tenant"]["id"] = directory

    manifest = assessment.build(
        RunSet(run_set.runs + [evaluate(rules(), satellite)]),
        documents + [satellite],
        engine_version="0.3.0",
        created_at="2026-08-08T18:00:00Z",
    )["canonical"]["manifest"]
    assert manifest["tenant"]["id"] == directory


def test_two_directory_identities_are_two_tenants():
    run_set, documents = one("site-spfx-current")
    other = json.loads((FIXTURES / "site-modern-clean.json").read_text())
    documents[0]["provenance"]["tenant"]["id"] = "9a1f0c7e-0000-4000-8000-0000000000a1"
    other["provenance"]["tenant"]["id"] = "9a1f0c7e-0000-4000-8000-0000000000b2"

    with pytest.raises(assessment.Mismatch, match="more than one directory"):
        assessment.build(
            RunSet(run_set.runs + [evaluate(rules(), other)]),
            documents + [other],
            engine_version="0.3.0",
            created_at="2026-08-08T18:00:00Z",
        )


def test_an_identity_kind_nobody_defined_is_refused():
    documents = [json.loads((FIXTURES / "site-spfx-current.json").read_text())]
    documents[0]["provenance"]["identity_kind"] = "hopeful"
    with pytest.raises(assessment.Mismatch):
        assessment.build(
            RunSet([evaluate(rules(), documents[0])]),
            documents,
            engine_version="0.3.0",
            created_at="2026-08-08T18:00:00Z",
        )


# ---------------------------------------------------------------------------
# the manifest describes the evidence underneath it, or there is no assessment
# ---------------------------------------------------------------------------


def one(name: str) -> tuple[RunSet, list[dict]]:
    documents = [json.loads((FIXTURES / f"{name}.json").read_text())]
    return RunSet([evaluate(rules(), documents[0])]), documents


def test_the_tenant_is_read_from_the_evidence_and_not_supplied():
    """It used to be a free string. The manifest could name a tenant that
    appears nowhere in the documents underneath it, and the digests would then
    prove that contradiction unchanged for as long as anyone kept the file."""
    tenant = built()["canonical"]["manifest"]["tenant"]
    assert tenant["host"] == "contoso.sharepoint.com"
    # Null, and required to be present. No collection path for the directory
    # id has been proven on a tenant, so the honest answer is that nobody read
    # it — which is not the same as the field not existing.
    assert tenant["id"] is None


def test_a_manifest_that_would_contradict_the_evidence_is_refused():
    run_set, documents = one("site-spfx-current")
    with pytest.raises(assessment.Mismatch, match="somebody-elses"):
        assessment.build(
            run_set,
            documents,
            engine_version="0.3.0",
            created_at="2026-08-08T18:00:00Z",
            tenant="somebody-elses.sharepoint.com",
        )


def test_two_tenants_are_two_assessments():
    """Not one bigger one: every count in the summary would be a sum across
    estates nobody manages together."""
    run_set, documents = one("site-spfx-current")
    other = json.loads((FIXTURES / "site-modern-clean.json").read_text())
    other["provenance"]["tenant"]["host"] = "fabrikam.sharepoint.com"
    with pytest.raises(assessment.Mismatch, match="more than one host"):
        assessment.build(
            RunSet(run_set.runs + [evaluate(rules(), other)]),
            documents + [other],
            engine_version="0.3.0",
            created_at="2026-08-08T18:00:00Z",
        )


def test_evidence_that_did_not_produce_these_runs_is_refused():
    """The digests prove nothing moved after the fact. They cannot prove the
    two halves ever belonged together, and without that every finding could
    cite evidence that never produced it."""
    run_set, _ = one("site-spfx-current")
    unrelated = [json.loads((FIXTURES / "site-modern-clean.json").read_text())]
    with pytest.raises(assessment.Mismatch, match="does not contain"):
        assessment.build(
            run_set,
            unrelated,
            engine_version="0.3.0",
            created_at="2026-08-08T18:00:00Z",
        )


@pytest.mark.parametrize(
    "names,summary,kinds",
    [
        (["site-spfx-current", "site-modern-clean"], "single", ["delegated"]),
        (["list-class-content", "list-within-limit"], "single", ["application"]),
        (
            ["site-spfx-current", "list-class-content"],
            "multiple",
            ["application", "delegated"],
        ),
        (["site-imported-inventory"], "not-established", []),
    ],
    ids=["all delegated", "all application", "two kinds", "identity not recorded"],
)
def test_the_identity_is_summarised_and_never_averaged(names, summary, kinds):
    """The manifest holds a statement about a set of documents, so it may not
    wear the name of a statement about one. It used to say `mixed`, which is
    not an identity anybody can authenticate as, and `imported`, which answers
    how the evidence arrived rather than who observed it.

    `not-established` is the honest reading of an export that does not name its
    collecting identity. Calling that identity `imported` said we knew
    something we did not.
    """
    identity = built(names=names)["canonical"]["manifest"]["identity"]
    assert identity == {"summary": summary, "kinds": kinds}


@pytest.mark.parametrize(
    "names,summary,kinds",
    [
        (["site-spfx-current", "site-modern-clean"], "single", ["collected"]),
        (["site-imported-inventory"], "single", ["imported"]),
        (
            ["site-spfx-current", "site-imported-inventory"],
            "multiple",
            ["collected", "imported"],
        ),
    ],
    ids=["all collected", "all imported", "both"],
)
def test_acquisition_is_summarised_separately(names, summary, kinds):
    """An archive with both halves has one whose collection completeness this
    engine can speak to and one whose it cannot, and a reader has to be able to
    see that without opening every document."""
    acquisition = built(names=names)["canonical"]["manifest"]["acquisition"]
    assert acquisition == {"summary": summary, "kinds": kinds}


def test_an_import_that_names_its_collector_keeps_that_identity():
    """The case the old model could not express at all: one field cannot hold
    both `who observed this` and `how it got here`, so an export that recorded
    a delegated collection was flattened into `imported` and the identity was
    lost."""
    documents = [json.loads((FIXTURES / "site-imported-inventory.json").read_text())]
    documents[0]["provenance"]["identity_kind"] = "delegated"

    manifest = assessment.build(
        RunSet([evaluate(rules(), documents[0])]),
        documents,
        engine_version="0.3.0",
        created_at="2026-08-08T18:00:00Z",
    )["canonical"]["manifest"]

    assert manifest["identity"] == {"summary": "single", "kinds": ["delegated"]}
    assert manifest["acquisition"] == {"summary": "single", "kinds": ["imported"]}
