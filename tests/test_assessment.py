"""An assessment carries what produced it, and proves it did not move.

`build` assembles one; `verify` checks one that arrived. They are separate on
purpose: verifying is what a consumer does to something somebody else made,
and it must not need the code that made it.
"""

from __future__ import annotations

import json

import jsonschema
import pytest
from referencing import Registry, Resource

from conftest import DATA
from m365_governance import assessment
from m365_governance.engine import evaluate
from m365_governance.loader import load_rules
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
        tenant=overrides.pop("tenant", "contoso.sharepoint.com"),
        identity_kind=overrides.pop("identity_kind", "delegated"),
        created_at=overrides.pop("created_at", "2026-08-08T18:00:00Z"),
        **overrides,
    )


def validator() -> jsonschema.Draft202012Validator:
    documents = {}
    for path in SCHEMAS.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        documents[document["$id"]] = document
    registry = Registry().with_resources(
        (uri, Resource.from_contents(document)) for uri, document in documents.items()
    )
    root = documents["https://ph7x.com/schemas/m365-governance/assessment/1.0.0"]
    return jsonschema.Draft202012Validator(root, registry=registry)


def test_the_committed_sample_matches_its_schema():
    errors = sorted(validator().iter_errors(json.loads(SAMPLE.read_text())), key=str)
    assert not errors, errors[0].message


def test_what_the_engine_builds_matches_its_schema():
    errors = sorted(validator().iter_errors(built()), key=str)
    assert not errors, errors[0].message


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


def test_the_manifest_is_not_hashed_by_the_digests_it_is_described_by():
    """It carries the id, and the id derives from those digests. Hashing it
    there would ask the identity to contain itself."""
    assert "manifest" not in built()["canonical"]["hashes"]["canonical_parts"]


def test_a_label_never_changes_the_identity():
    """What somebody calls it is not what it is."""
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


def test_an_identity_kind_nobody_defined_is_refused():
    with pytest.raises(ValueError):
        built(identity_kind="hopeful")
