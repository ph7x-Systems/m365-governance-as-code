"""The capability manifest: what this engine says it can do.

Nothing here reaches a tenant, and the manifest never does either — it is
computed from the slice registry, the rules, the fixtures and the schemas.

THE TWO THINGS THESE TESTS EXIST FOR:

1. **It is derived, so it cannot drift.** Every assertion below compares the
   manifest against the object that owns the fact, not against a copy. A test
   that pinned a count or a rule id would be the second authority the manifest
   exists to remove.
2. **It describes what is, never what is planned.** A capability nobody has run
   against a tenant says so; a permission nobody has established says so.
"""

from __future__ import annotations

import json

from m365_governance import capabilities, collecting, registry
from m365_governance.loader import load_rules
from m365_governance.resources import packaged

SCHEMAS = registry.SchemaRegistry.load(packaged("schemas"))
MANIFEST = capabilities.manifest()


def test_the_manifest_validates_against_the_contract_it_declares():
    contract = MANIFEST["$schema"]

    assert contract == registry.contract("capability-manifest")
    assert list(SCHEMAS.validator(contract).iter_errors(MANIFEST)) == []


def test_every_slice_appears_exactly_once():
    """Derived from the registry, so a new slice is described the day it exists
    rather than the day somebody remembers to add it here."""
    named = [c["name"] for c in MANIFEST["capabilities"]]

    assert sorted(named) == sorted(collecting.SLICES)
    assert len(named) == len(set(named))


def test_each_capability_carries_what_its_slice_declares():
    for capability in MANIFEST["capabilities"]:
        chosen = collecting.SLICES[capability["name"]]
        collector = capability["collector"]

        assert collector["kind"] == chosen.source
        assert collector["reads"] == list(chosen.reads)
        assert collector["live_validation"] == chosen.live
        assert capability["describes"] == chosen.describes


def test_a_permission_nobody_established_says_so_rather_than_being_empty():
    """An invented permission is worse than an admitted gap: somebody grants it."""
    for capability in MANIFEST["capabilities"]:
        permissions = capability["collector"]["permissions"]
        assert permissions, capability["name"]
        chosen = collecting.SLICES[capability["name"]]
        if not chosen.permissions:
            assert permissions == ["not-established"]


def test_the_rules_a_capability_supports_are_the_ones_that_can_decide():
    """Derived by running them, and the difference is not cosmetic.

    Matching on workload and resource type alone answers "which rules could
    apply to a document of this shape", which for SharePoint is nearly all of
    them: `classification` came back owning fifteen rules it says nothing
    about. A rule belongs to a slice when it can reach an answer from what the
    slice collected.
    """
    from m365_governance.engine import evaluate
    from m365_governance.loader import load_json
    from m365_governance.results import Outcome

    rules = [r.data for r in load_rules(packaged("rules"))]

    for capability in MANIFEST["capabilities"]:
        chosen = collecting.SLICES[capability["name"]]
        if not chosen.produces_findings:
            continue
        # Every shape the slice declares, not one of them: a collector with
        # a branch feeds rules its primary fixture never reaches.
        decidable = set()
        for name in (chosen.shaped_like, *chosen.also_shaped_like):
            document = _fixture(name, load_json)
            decidable |= {
                result.rule_id
                for result in evaluate(rules, document).results
                if result.outcome is not Outcome.UNKNOWN
            }
        assert set(capability["consumed_by"]) == decidable, chosen.name
        assert decidable, f"{chosen.name} supports no rule and claims to"


def test_a_slice_no_rule_reads_names_what_does():
    """The price of the exception to the twin rule, kept in the manifest too."""
    for capability in MANIFEST["capabilities"]:
        chosen = collecting.SLICES[capability["name"]]
        if chosen.produces_findings:
            continue
        assert capability["consumed_by"] == []
        assert capability["consumer"] != "governance rules"
        assert capability["consumer"].strip()


def test_the_workload_a_capability_produces_is_read_from_its_own_evidence():
    from m365_governance.loader import load_json

    for capability in MANIFEST["capabilities"]:
        chosen = collecting.SLICES[capability["name"]]
        resource = _fixture(chosen.shaped_like, load_json)["resource"]

        assert capability["produces"]["workload"] == resource["workload"]
        assert capability["produces"]["resource_type"] == resource["type"]


def test_every_rule_carries_its_basis_and_its_limitations():
    """An outcome without a basis is an opinion with a severity attached."""
    on_disk = {r.data["id"]: r.data for r in load_rules(packaged("rules"))}

    assert {r["id"] for r in MANIFEST["rules"]} == set(on_disk)
    for rule in MANIFEST["rules"]:
        source = on_disk[rule["id"]]
        assert rule["basis"]["type"] == source["basis"]["type"]
        # A `convention` has no sources by design: the threshold is ours, and
        # the rationale is what carries it. Requiring a source there would
        # push somebody to attach a vendor page that does not say the thing.
        if rule["basis"]["type"] == "convention":
            assert rule["basis"]["rationale"], rule["id"]
        else:
            assert rule["basis"]["sources"], rule["id"]
        assert rule["service"] == source["service"]
        assert "passes_without_resolving" in rule["limitations"]


def test_every_contract_this_engine_holds_is_listed():
    assert MANIFEST["contracts"] == sorted(SCHEMAS.contracts())
    assert MANIFEST["$schema"] in MANIFEST["contracts"]


def test_the_versions_come_from_the_engine_and_the_bundle():
    from m365_governance import __version__

    assert MANIFEST["engine_version"] == __version__
    assert MANIFEST["contract_version"] == collecting._contract_version()


def test_nothing_planned_appears_and_nothing_shipped_is_hidden():
    """The manifest describes what is, and a gap says so out loud.

    The conditional-access slice is the live case: its provider has read a real
    tenant and the slice above it has not, so it is present with its own
    sentence rather than absent until the story is tidier.
    """
    entry = next(
        c for c in MANIFEST["capabilities"] if c["name"] == "conditional-access"
    )

    assert entry["collector"]["kind"] == "graph"
    assert "not live-validated" in entry["collector"]["live_validation"]
    assert entry["collector"]["permissions"] == ["Policy.Read.All"]


def test_the_command_prints_the_same_document_it_publishes(capsys):
    from m365_governance.cli import main

    assert main(["capabilities", "--format", "json"]) == 0
    printed = json.loads(capsys.readouterr().out)

    assert printed == MANIFEST

    assert main(["capabilities"]) == 0
    text = capsys.readouterr().out
    for capability in MANIFEST["capabilities"]:
        assert capability["name"] in text


def test_the_command_reaches_no_tenant_and_reads_no_evidence():
    """It describes the engine. A network or a tenant would be a different
    command, and this one has no argument that could name either."""
    from m365_governance.cli import _build_parser

    actions = {
        action.dest
        for action in _build_parser()
        ._subparsers._group_actions[0]  # type: ignore[union-attr]
        .choices["capabilities"]
        ._actions
    }

    assert actions <= {"help", "rules", "format"}


def _fixture(name: str, load_json):
    for folder in ("sharepoint", "entra"):
        path = packaged("fixtures") / folder / f"{name}.json"
        if path.is_file():
            return load_json(path)
    raise AssertionError(f"no fixture {name}")


def test_every_published_rule_is_fed_by_a_published_capability():
    """THE CATALOGUE'S OWN COVERAGE, and the metric this phase is measured by.

    A rule nobody can collect for answers `unknown` against every tenant, for
    ever, which is honest and is also product debt. The manifest is where that
    debt has to be visible, so this asserts the number rather than trusting a
    reading of it.

    It caught a real one. The manifest said `permissions` fed a single rule
    when it feeds three: a collector with a branch produces more than one
    shape, and the catalogue asked one of them which rules it decides. Two
    published rules looked uncollectable and were not.
    """
    from m365_governance import capabilities

    document = capabilities.manifest()
    fed = set()
    for capability in document["capabilities"]:
        fed |= set(capability.get("consumed_by") or [])
    published = {rule["id"] for rule in document["rules"]}
    assert not published - fed, (
        f"published rules no capability feeds: {sorted(published - fed)}. Each "
        "one answers unknown against every tenant, and the catalogue is where "
        "that has to be visible."
    )


def test_a_collector_with_a_branch_declares_every_shape_it_produces():
    """`permissions` collects a unique scope count only in the branch that
    walks items. Pairing it with a fixture from the other branch published a
    collector as feeding one rule while it fed three, and nothing went red."""
    from m365_governance import capabilities, collecting

    chosen = collecting.SLICES["permissions"]
    assert chosen.also_shaped_like, (
        "the permissions slice stopped declaring its second shape, and the "
        "catalogue will under-report it again"
    )
    rules = [r.data for r in load_rules(packaged("rules"))]
    primary = capabilities._decidable(rules, capabilities._named(chosen.shaped_like))
    every = set().union(
        *(capabilities._decidable(rules, d) for d in capabilities._shapes(chosen))
    )
    assert every > primary, (
        "the second shape adds nothing, so either the fixture is wrong or the "
        "declaration is decoration"
    )
