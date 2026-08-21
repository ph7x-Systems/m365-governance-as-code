"""The registry, and the ten things it has to refuse.

A registry that only resolves is a dictionary. What makes this one worth having
is the list of documents it will not accept and the resolutions it will not
perform: an unknown contract, a file whose insides disagree with its
registration, two files claiming one identity, a reference that would be
satisfied from the network.

The archived pair in here is real history rather than a construction. The
schema is `evidence/1.2.0` exactly as it was before containment and the
identity split, and the document beside it was written under it, with
`tenant_id` as a GUID and no `scope` on its resource. Neither has been edited
to fit a convention it predates, because editing an archive to match today is
the failure this whole step exists to prevent.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest
from referencing.exceptions import Unresolvable

from conftest import DATA
from m365_governance import registry as registry_module
from m365_governance.registry import (
    RegistryError,
    SchemaRegistry,
    Undeclared,
    UnknownContract,
)

SCHEMAS = DATA / "schemas"
FIXTURES = DATA / "fixtures" / "sharepoint"
ARCHIVE = DATA / "fixtures" / "archive"

# From the registry, never written out again. A literal version in a test is a
# second representation of the one thing this module is strictest about, and it
# goes stale in silence: the test keeps passing against the version it names
# while the engine ships another.
EVIDENCE = registry_module.contract("evidence")
EVIDENCE_1_2_0 = "https://ph7x.com/schemas/m365-governance/evidence/1.2.0"


def contracts() -> SchemaRegistry:
    return SchemaRegistry.load(SCHEMAS)


def evidence(name: str = "site-two-owners") -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def elsewhere(tmp_path, edit=None):
    """A copy of the schema tree, so a sabotaged registry is never this one."""
    root = tmp_path / "schemas"
    shutil.copytree(SCHEMAS, root)
    if edit:
        edit(root)
    return root


# ---------------------------------------------------------------------------
# the three identifiers, kept apart
# ---------------------------------------------------------------------------


def test_the_dialect_and_the_contract_are_different_fields():
    """Inside a schema document `$schema` names the JSON Schema dialect and
    `$id` names the pH7x contract. One field meaning both is the confusion the
    registry exists to prevent."""
    for path in sorted(SCHEMAS.rglob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["$schema"] == registry_module.DIALECT
        assert document["$id"].startswith("https://ph7x.com/schemas/")
        assert document["$schema"] != document["$id"]


def test_an_instance_declares_the_contract_that_validates_it():
    """And it cannot declare another one. `$schema` is `const` against the
    owning `$id`, so the two are not two things kept in step by hand."""
    document = json.loads((SCHEMAS / "evidence.schema.json").read_text())
    assert document["properties"]["$schema"]["const"] == document["$id"]
    assert "$schema" in document["required"]


def test_no_instance_contract_keeps_a_second_version_field():
    """`schema_version: "1.0"` sat beside an `$id` ending in `/1.2.0`: two
    representations of one thing, in a pattern that could not even express the
    other. There is one now, and it is the declaration."""
    for name in ("evidence", "run", "run-set", "assessment", "comparison"):
        document = json.loads((SCHEMAS / f"{name}.schema.json").read_text())
        properties = document.get("properties", {})
        assert "schema_version" not in properties
        assert "run_schema_version" not in properties
        assert "diff_schema_version" not in properties


def test_every_contract_identity_is_exact_semver():
    for contract in contracts().contracts():
        assert registry_module.CONTRACT.match(contract), contract


@pytest.mark.parametrize("alias", ["latest", "v2", "2.0", "stable"])
def test_a_moving_version_is_not_a_contract(alias):
    """An archive resolved through a pointer that moves is an archive that
    changes meaning without anybody editing it."""
    assert not registry_module.CONTRACT.match(
        f"https://ph7x.com/schemas/m365-governance/evidence/{alias}"
    )


# ---------------------------------------------------------------------------
# 1. an instance's contract resolves offline
# ---------------------------------------------------------------------------


def test_the_contract_a_document_declares_resolves_offline():
    document = evidence()
    assert document["$schema"] == EVIDENCE
    assert contracts().problems(document) == []


def test_the_registry_maps_contract_to_path_and_digest():
    manifest = contracts().as_manifest()
    assert manifest[EVIDENCE]["path"] == "evidence.schema.json"
    assert len(manifest[EVIDENCE]["digest"]) == 64
    assert manifest[EVIDENCE_1_2_0]["path"] == "archive/evidence-1.2.0.schema.json"


# ---------------------------------------------------------------------------
# 2. an unknown contract is refused
# ---------------------------------------------------------------------------


def test_a_contract_this_engine_does_not_hold_is_refused():
    document = evidence()
    document["$schema"] = "https://ph7x.com/schemas/m365-governance/evidence/9.9.9"
    with pytest.raises(UnknownContract):
        contracts().validator_for(document)


def test_a_document_that_declares_nothing_is_refused():
    """Silence is not a default. Choosing a schema for it would be guessing
    which contract somebody meant, and getting that wrong looks like a finding
    about a tenant rather than a mistake about a file."""
    document = evidence()
    document.pop("$schema")
    with pytest.raises(Undeclared):
        contracts().validator_for(document)


# ---------------------------------------------------------------------------
# 3. a declaration that disagrees with the contract is refused
# ---------------------------------------------------------------------------


def test_declaring_one_contract_and_matching_another_is_refused():
    """The archived 1.2.0 contract is a real schema this registry holds, so
    this document resolves — and then fails, because `const` says the
    declaration and the validating schema are the same string."""
    document = evidence()
    document["$schema"] = EVIDENCE_1_2_0
    problems = contracts().problems(document)
    assert problems, "a document validated against a contract it does not claim"


# ---------------------------------------------------------------------------
# 4 and 5. registration invariants
# ---------------------------------------------------------------------------


def test_a_file_whose_id_differs_from_its_registration_is_refused(tmp_path):
    """Registration is by the `$id` inside the file, so the two cannot drift.
    A file that declares an identity it was not filed under would answer a
    question nobody asked it."""

    def sabotage(root):
        path = root / "evidence.schema.json"
        document = json.loads(path.read_text())
        document["$id"] = "https://ph7x.com/schemas/m365-governance/evidence/7.7.7"
        path.write_text(json.dumps(document))

    with pytest.raises(RegistryError, match="does not hold"):
        SchemaRegistry.load(elsewhere(tmp_path, sabotage))


def test_two_files_claiming_one_identity_are_refused(tmp_path):
    """Otherwise a consumer resolves whichever was read first, which is a
    property of the filesystem rather than of the contract."""

    def sabotage(root):
        shutil.copy(root / "evidence.schema.json", root / "evidence-copy.schema.json")

    with pytest.raises(RegistryError, match="registered twice"):
        SchemaRegistry.load(elsewhere(tmp_path, sabotage))


def test_a_schema_in_another_dialect_is_refused(tmp_path):
    def sabotage(root):
        path = root / "evidence.schema.json"
        document = json.loads(path.read_text())
        document["$schema"] = "http://json-schema.org/draft-07/schema#"
        path.write_text(json.dumps(document))

    with pytest.raises(RegistryError, match="dialect"):
        SchemaRegistry.load(elsewhere(tmp_path, sabotage))


# ---------------------------------------------------------------------------
# 6 and 7. references resolve through the registry, and stay strict
# ---------------------------------------------------------------------------


def test_a_cross_file_reference_resolves_through_the_registry():
    """The assessment references the run set, which references the run. All of
    it is held here, so none of it is fetched."""
    document = json.loads(
        (DATA / "fixtures" / "assessment" / "three-resources.json").read_text()
    )
    assert contracts().problems(document) == []


def test_invalid_referenced_content_is_still_invalid():
    """A reference is not a hole. Breaking an evidence document inside an
    assessment has to fail through the reference, not pass because the outer
    shape is intact."""
    document = json.loads(
        (DATA / "fixtures" / "assessment" / "three-resources.json").read_text()
    )
    document["canonical"]["evidence"][0]["resource"].pop("parent")
    problems = contracts().problems(document)
    assert any("parent" in problem for problem in problems), problems


def test_a_reference_the_registry_does_not_hold_is_an_error_not_a_fetch(tmp_path):
    def sabotage(root):
        path = root / "assessment.schema.json"
        document = json.loads(path.read_text())
        document["$defs"]["canonical"]["properties"]["run_set"]["$ref"] = (
            "https://example.invalid/schemas/run-set/1.0.0"
        )
        path.write_text(json.dumps(document))

    with pytest.raises(RegistryError, match="not self-contained"):
        SchemaRegistry.load(elsewhere(tmp_path, sabotage))


# ---------------------------------------------------------------------------
# 8. nothing is resolved from the network or the filesystem
# ---------------------------------------------------------------------------


def test_nothing_resolves_off_the_registry():
    """The acceptance property. A schema the registry does not hold must not
    be satisfiable from anywhere else — not a URL, and not a file sitting next
    to the one being read."""
    held = contracts()
    validator = held.validator(EVIDENCE)

    # `referencing` raises rather than fetching, and this asserts that it is
    # the registry answering rather than a network stack that happens to be
    # offline while the test runs.
    with pytest.raises(Unresolvable):
        validator._resolver.lookup(
            "https://ph7x.com/schemas/m365-governance/ghost/1.0.0"
        )


# ---------------------------------------------------------------------------
# 9 and 10. an archive keeps its own contract
# ---------------------------------------------------------------------------


def test_an_archived_document_validates_against_its_own_version():
    """Real history: this document was written under `evidence/1.2.0`, before
    containment and before identity and acquisition were separated. It still
    validates, against the contract it was written under."""
    document = json.loads((ARCHIVE / "evidence-1.2.0-site.json").read_text())
    held = contracts()

    errors = list(held.validator(EVIDENCE_1_2_0).iter_errors(document))
    assert not errors, errors[0].message


def test_the_current_contract_never_silently_reinterprets_an_older_document():
    """The same document against today's evidence schema. It fails, and that is
    the point: a new version is a different contract, not a new reading of an
    old one. Turning that document into a current one is a migration that
    produces a new document.
    """
    document = json.loads((ARCHIVE / "evidence-1.2.0-site.json").read_text())
    errors = list(contracts().validator(EVIDENCE).iter_errors(document))
    assert errors, "the current schema accepted a document written for 1.2.0"

    messages = " ".join(error.message for error in errors)
    assert "$schema" in messages or "acquisition" in messages


def test_the_validator_is_chosen_by_the_document_and_not_by_the_engine():
    """`validator_for` reads the declaration. Two documents declaring two
    contracts get two validators, and neither is 'whichever this engine ships
    today'."""
    held = contracts()

    current = evidence()
    archived = dict(current, **{"$schema": EVIDENCE_1_2_0})

    assert held.validator_for(current).schema["$id"] == EVIDENCE
    assert held.validator_for(archived).schema["$id"] == EVIDENCE_1_2_0


def test_the_collector_declares_the_contract_the_engine_ships():
    """PowerShell cannot import the registry, so the URI is written out in the
    collector. This is the gate that keeps that copy from drifting."""
    collector = (
        DATA / "collectors" / "powershell" / "sharepoint" / "modules" / "Evidence.psm1"
    ).read_text(encoding="utf-8")
    assert registry_module.contract("evidence") in collector


def test_a_published_version_still_has_the_shape_it_published() -> None:
    """A version is a promise, and the tree cannot tell a kept one from a broken
    one.

    Editing a schema without moving its ``$id`` leaves the promise's name and
    changes what it promises. Both a correct edit and that one look identical
    from here — a changed file — so the only witness is a digest recorded when
    the version was published. That is what this reads.

    It is not a duplicate of the generated manifest. The manifest is rewritten
    from whatever is on disk, so it agrees with a silent edit by construction;
    this file is written by hand, once per version, and disagrees.
    """
    ledger = json.loads(
        (DATA / "published-contracts.json").read_text(encoding="utf-8")
    )["contracts"]

    held = {}
    for path in sorted(SCHEMAS.rglob("*.schema.json")):
        raw = path.read_bytes()
        held[json.loads(raw)["$id"]] = (hashlib.sha256(raw).hexdigest(), path)

    for uri, (digest, path) in sorted(held.items()):
        assert uri in ledger, (
            f"{path.name} declares {uri}, which is not in the ledger. A new "
            "version is recorded there in the same change that introduces it."
        )
        assert ledger[uri] == digest, (
            f"{uri} is not the shape that was published under that name — "
            f"{path.name} has changed. A changed shape is a new version: move "
            "the `$id`, archive the old text, and record the new digest."
        )

    for uri in sorted(set(ledger) - set(held)):
        raise AssertionError(
            f"{uri} was published and this engine no longer holds it. A "
            "consumer holding a document of that version can no longer have it "
            "validated: archive the schema rather than dropping it."
        )
