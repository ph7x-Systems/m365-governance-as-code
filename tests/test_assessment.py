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


def test_the_manifest_is_covered_except_for_what_cannot_be():
    """`tenant`, `created_at` and `identity_kind` are facts about what was
    assessed, so changing one has to be detectable. An earlier version left the
    whole manifest out of the digests and a workspace test found the hole: an
    assessment could be relabelled as belonging to a different tenant and still
    verify."""
    assert "manifest" in built()["canonical"]["hashes"]["canonical_parts"]

    moves = (
        ("tenant", "somebody-elses.sharepoint.com", True),
        ("created_at", "2020-01-01T00:00:00Z", True),
        ("identity_kind", "application", True),
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
    assert built()["canonical"]["manifest"]["tenant"] == "contoso.sharepoint.com"


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
    other["provenance"]["tenant_id"] = "fabrikam.sharepoint.com"
    with pytest.raises(assessment.Mismatch, match="more than one tenant"):
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
    "names,expected",
    [
        (["site-spfx-current", "site-modern-clean"], "delegated"),
        (["list-class-content", "list-within-limit"], "application"),
        (["site-spfx-current", "list-class-content"], "mixed"),
        (["site-imported-inventory"], "imported"),
    ],
    ids=["all delegated", "all application", "mixed", "imported"],
)
def test_the_identity_describes_what_observed_it(names, expected):
    """`mixed` is a real answer and never the reassuring one: part of the
    archive is tenant-wide and part of it is one person's view, and the reader
    resolves that per document rather than by taking an average."""
    assert built(names=names)["canonical"]["manifest"]["identity_kind"] == expected
