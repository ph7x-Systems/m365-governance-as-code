"""From a finding to the observation that supports it, mechanically.

THE ACCEPTANCE FOR THE WORD `proven`. Open a canonical artefact, pick one
finding, reach the facts it used, from each fact block reach the evidence
document that supplied it, and from that document reach the acquisition -- with
**no human report, no prior knowledge of how any collector is implemented, and
without calling the engine again**.

Everything this test is allowed to use is a lookup in the artefact, plus the
digest definition the product publishes. It imports the engine to BUILD the
artefact, and then walks it with plain dictionary access, because a walk that
needed the engine would be internal provenance rather than the product's.
"""

import hashlib
import json

from m365_governance.cli import main


def digest_of(document: dict) -> str:
    """The digest, recomputed the way a consumer recomputes it.

    Canonical JSON as `canonical-json-and-digests` defines it: sorted keys, no
    whitespace, UTF-8, unescaped. Deliberately written out here rather than
    imported, because a consumer holding a bundle has this definition and not
    this package.
    """
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()[:16]


def test_one_finding_walks_back_to_the_observations_that_support_it(tmp_path):
    fixture = (
        "src/m365_governance/data/fixtures/sharepoint/list-catalog-over-hard-limit.json"
    )
    out = tmp_path / "assessment.json"

    assert main(["assess", "--evidence", fixture, "--out", str(out)]) in (0, 1)

    # ── from here on, nothing but the artefact ───────────────────────────────
    assessment = json.loads(out.read_text(encoding="utf-8"))
    canonical = assessment["canonical"]
    runs = canonical["run_set"]["runs"]
    evidence = canonical["evidence"]

    findings = [
        (run, result)
        for run in runs
        for result in run["results"]
        if result["outcome"] == "fail"
    ]
    assert findings, "the fixture is chosen because it produces a finding"
    run, finding = findings[0]

    # 1 · the finding names the facts it used.
    paths = [entry["path"] for entry in finding["evidence_used"]]
    assert paths, "a finding that names no evidence cannot be walked back"

    # 2 · the run says which document supplied each fact block.
    attribution = run["attribution"]
    assert attribution, (
        "the run carries no attribution, so this artefact cannot answer which "
        "observation supports its own finding"
    )

    # 3 · the documents are in the artefact, identified by recomputing.
    by_digest = {digest_of(document): document for document in evidence}

    reached = []
    for path in paths:
        block = path.split(".", 1)[0]
        assert block in attribution, (
            f"the finding used `{path}` and nothing says which document "
            f"supplied `{block}`"
        )
        source = attribution[block]["document"]
        assert source in by_digest, (
            f"`{block}` is attributed to {source}, which is not one of the "
            "documents this artefact carries"
        )
        reached.append((path, by_digest[source]))

    # 4 · and each document carries the acquisition, not a name to look up.
    for path, document in reached:
        provenance = document["provenance"]
        assert provenance.get("collector"), f"{path}: no collector on the source"
        assert provenance.get("collected_at"), f"{path}: no moment on the source"
        block = path.split(".", 1)[0]
        assert block in document["facts"], (
            f"{path} was attributed to a document that does not carry `{block}`"
        )

    # THE CLAIM, STATED AS WHAT WAS ACTUALLY REACHED.
    assert len(reached) == len(paths)


def test_the_walk_uses_no_prose_from_the_human_report(tmp_path):
    """The Markdown report is for a person and is not evidence of anything.

    An artefact whose chain is only recoverable by reading sentences is an
    artefact a machine cannot check, and `software establishes, people decide`
    applies to this software too: a person must not have to reconstruct by hand
    a relation the product claims as proven.
    """
    fixture = (
        "src/m365_governance/data/fixtures/sharepoint/list-catalog-over-hard-limit.json"
    )
    out = tmp_path / "assessment.json"
    main(["assess", "--evidence", fixture, "--out", str(out)])

    assessment = json.loads(out.read_text(encoding="utf-8"))
    runs = assessment["canonical"]["run_set"]["runs"]

    # Every link used above is a structured field. None of them is a string
    # anybody has to parse for meaning.
    for run in runs:
        assert isinstance(run["attribution"], dict)
        for block, entry in run["attribution"].items():
            assert isinstance(block, str) and "." not in block
            assert entry["document"].startswith("sha256:")
            assert len(entry["document"]) == 23
            # THE DESCRIPTION BESIDE THE IDENTITY. A surface that opens a run
            # without its documents cannot resolve a digest, and would have
            # shown a reader a hash and asked them to believe it.
            assert entry["collector"] and entry["collected_at"]
