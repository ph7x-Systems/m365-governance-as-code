"""What a bundle's identity covers, and where the artefact ends.

`bundle: proven` says an artefact was produced and never which one, so the
stage above it -- a consumer opening a bundle -- can never be shown to be about
the same artefact. The identity closes that, and it has to be exact: two
sentences that cannot be tied to one object establish nothing together.

THREE PROPERTIES, AND EACH FAILED ONCE WHILE THIS WAS BEING BUILT.

    non-circular   the manifest holds the digest and is inside the tree the
                   digest covers, so hashing it whole asks for a fixed point
    complete       a declared identity that does not cover the whole artefact
                   is worse than none: a consumer repeats a value matching
                   nothing it holds
    closed         the artefact ends when the producer closes it. What a
                   consumer writes beside the runs afterwards is that
                   consumer's local state and was never part of what it opened
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from m365_governance import bundling, engine, loader, resources
from m365_governance.results import Run


@pytest.fixture
def produced(tmp_path) -> Path:
    """A bundle, made the way `run --bundle` makes one."""
    document = json.loads(
        (resources.packaged("fixtures") / "sharepoint" / "site-one-owner.json").read_text(
            encoding="utf-8"
        )
    )
    rules = [r.data for r in loader.load_rules(resources.packaged("rules"))]
    run: Run = engine.evaluate(rules, document)
    root = tmp_path / "bundle"
    bundling.write(root, [run], [document], fmt="markdown")
    return root


def _declared(root: Path) -> str:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))[
        "bundle_digest"
    ]


def test_the_declared_identity_is_the_identity_of_the_whole_artefact(produced):
    """NON-CIRCULAR AND COMPLETE AT ONCE, which is the difficult half.

    Leaving the manifest out entirely would break the circle and leave the run
    list and the bundle version outside the identity -- so a bundle could lose
    a run and keep its digest. Only the FIELD is left out.
    """
    assert _declared(produced) == bundling.digest_of(produced)


def test_the_rule_does_not_depend_on_the_value_it_leaves_out(produced):
    """The first attempt applied the strip only when the field was present, so
    the same document hashed two ways: as raw bytes before the value existed
    and as canonical JSON after. The digest a manifest declared never equalled
    the digest of the tree holding that manifest."""
    manifest = produced / "manifest.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    declared = document.pop("bundle_digest")
    manifest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    assert bundling.digest_of(produced) == declared, (
        "removing the declaration changed the identity, so the identity "
        "depends on the value it exists to leave out"
    )


def test_a_consumer_writing_beside_the_runs_does_not_change_what_it_opened(
    produced, tmp_path
):
    """THE FIRST TEST THE OWNER REQUIRED.

    Opening a workspace writes an index beside the runs. The artefact ended
    when the producer closed it, so the identity a consumer reads out of the
    copy it is working in must be the identity of what it was handed.
    """
    copy = tmp_path / "as-a-consumer-has-it"
    shutil.copytree(produced, copy)

    # What a consumer adds afterwards: an index, a workspace file, whatever.
    (copy / "workspace.json").write_text('{"opened": true}\n', encoding="utf-8")
    (copy / "runs" / ".index").write_text("local state\n", encoding="utf-8")

    assert _declared(copy) == _declared(produced), (
        "the identity a consumer reads changed because the consumer wrote "
        "beside the runs"
    )

    # And the artefact it was handed is untouched.
    for path in sorted(produced.rglob("*")):
        if path.is_file():
            mirror = copy / path.relative_to(produced)
            assert mirror.read_bytes() == path.read_bytes()


def test_changing_canonical_content_makes_the_old_identity_refuse(produced):
    """THE SECOND TEST THE OWNER REQUIRED.

    The boundary has to cut both ways. Local state added beside the runs is
    outside the identity; a file that belongs to the artefact is inside it, and
    editing one must move the digest away from what was declared.
    """
    declared = _declared(produced)
    run = next(
        path
        for path in (produced / "runs").rglob("run.json")
    )
    document = json.loads(run.read_text(encoding="utf-8"))
    document["results"][0]["message"] = "something else entirely"
    run.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    assert bundling.digest_of(produced) != declared, (
        "a result's message was rewritten and the artefact still claims to be "
        "the same one"
    )


def test_renaming_a_run_moves_the_identity(produced):
    """A digest over concatenated contents is identical for a bundle whose
    files were renamed, and a consumer proving it opened `runs/a` when the
    artefact now calls it `runs/b` has proved nothing about what anybody
    holds."""
    declared = _declared(produced)
    run = next(path for path in (produced / "runs").iterdir() if path.is_dir())
    run.rename(run.parent / "renamed")

    assert bundling.digest_of(produced) != declared


# ---------------------------------------------------------------------------
# the rehearsal: everything the live measurement will do, except the tenant
# ---------------------------------------------------------------------------


def test_the_ladder_would_reach_the_top_if_the_acquisition_were_live(
    produced, monkeypatch
):
    """THE MEASUREMENT, REHEARSED OFFLINE.

    The live run is one shot and the credentials for it are not ours to
    arrange, so everything it does that fixtures CAN establish is established
    here: a bundle produced by the bundler, its identity declared inside it,
    that identity recorded on the stage, a consumer repeating the same
    identifier, and the ladder deriving its own conclusion.

    WHAT THIS DOES NOT ESTABLISH, and the reason the number stays at zero: the
    acquisition below it. The three stages beneath `bundle` are asserted here
    rather than observed, because a fixture cannot read a directory. That is
    exactly the gap the live run closes and the only one it needs to.

    NOTHING HERE TOUCHES THE SHIPPED REGISTER. The records are substituted for
    the length of this test, so no live proof is promoted by a rehearsal.
    """
    from m365_governance import live_proof

    declared = _declared(produced)

    # What `run --bundle` writes: the stage raised WITH the identity of the
    # artefact the run produced.
    draft = {
        "collector": "owners",
        "provenance": live_proof.EMITTED,
        "establishes": "full",
        "stages": {
            "acquisition": "proven",
            "evidence": "proven",
            "assessment": "attempted",
            "bundle": "not-attempted",
            "consumer": "not-attempted",
        },
    }
    raised = live_proof.upgrade_after_a_run(
        draft, evaluated=True, bundled=True, artifact_digest=declared
    )

    assert raised["stages"]["bundle"] == "proven"
    assert raised["bundle_digest"] == declared

    # The live run cannot raise `assessment` past `attempted` -- a result
    # cannot be traced back to the collector whose fact it read. A person
    # confirms it from the report, which is the step this rehearsal stands in
    # for rather than removes.
    raised["stages"]["assessment"] = "proven"

    # What the consumer returns, having opened a copy and read the identity out
    # of it. The value is repeated, never recomputed: what this establishes is
    # that the consumer opened the artefact identifying itself as the bundle
    # the producer recorded, and nothing about cryptographic verification.
    raised["stages"]["consumer"] = "proven"
    raised["consumer_proof"] = {
        "consumer": "a-separate-consumer",
        "consumer_version": "1.4.0",
        "independence": "separate-consumer",
        "observed_at": "2026-08-24",
        "artifact_digest": declared,
    }

    monkeypatch.setattr(
        live_proof, "records", lambda name: [raised] if name == "owners" else []
    )

    assert live_proof.incoherent("owners") == []
    assert live_proof.proof_state("owners") == "vertical-path-proven"


def test_the_rehearsal_promoted_nothing_in_the_shipped_register():
    """The register that ships is read after the rehearsal, unpatched.

    A rehearsal that left a capability higher than it was would be the exact
    thing the register exists to prevent, arriving through the test that was
    supposed to prove it could not.

    WHAT IS ASSERTED IS THAT THE REHEARSAL CHANGED NOTHING, not that the top of
    the ladder is empty. Two capabilities reached it on 2026-08-24 through real
    records, so an emptiness check here would now be asserting the register is
    wrong. `owners` is the control: it has an acquisition and no bundle, and a
    rehearsal that promoted anything would move it first.
    """
    from m365_governance import live_proof

    assert live_proof.population()["vertical-path-proven"] == [
        "brand-center",
        "conditional-access",
        "tenant-governance",
        "tenant-sharing",
    ]
    assert live_proof.proof_state("owners") == "positive-acquisition-observed"
