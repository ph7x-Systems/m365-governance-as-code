"""The artefact a consumer proves it can open, and the engine's half of that.

`consumer` is the one stage of product path assurance this engine cannot
raise: somebody independent opening the artefact is the stage a program
certifying it would be certifying itself. So the engine's whole part is to
publish something that CAN be proved, with an identity stable enough for a
proof to point at, and then to stop.

These tests hold the two properties that make such a proof mean anything: the
artefact is reproducible, so its digest identifies it rather than the machine
that built it; and nothing here writes `consumer: proven`.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "src" / "m365_governance" / "data" / "reference"


@pytest.fixture(scope="module")
def described() -> dict:
    return json.loads((REFERENCE / "reference.json").read_text(encoding="utf-8"))


def test_the_reference_bundle_is_what_this_engine_produces():
    """REGENERATED AND COMPARED, not trusted.

    A proof names a digest. If regenerating produced different bytes the digest
    would identify the machine that built it rather than the artefact, and
    every consumer proof pointing at it would silently stop pointing at
    anything.
    """
    finished = subprocess.run(
        [sys.executable, "tools/reference-bundle.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_it_carries_the_identity_a_proof_has_to_point_at(described):
    """A consumer proof names five things and this artefact has to supply the
    one nobody else can: which artefact. Without a digest here, a proof either
    names nothing or names something it invented."""
    assert described["digest"].startswith("sha256:")
    assert described["engine_version"]
    assert described["contracts"]["run"].startswith("https://")


def test_the_digest_covers_the_paths_and_not_only_the_bytes():
    """A digest over concatenated contents is the same for a bundle whose files
    were renamed. A consumer proving it opened `runs/a` when the artefact now
    calls it `runs/b` has proved nothing about the artefact anybody holds."""
    sys.path.insert(0, str(ROOT / "tools"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "reference_bundle", ROOT / "tools" / "reference-bundle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import shutil
    import tempfile

    copy = pathlib.Path(tempfile.mkdtemp()) / "reference"
    shutil.copytree(REFERENCE, copy)
    before = module.digest_of(copy)

    run = next(p for p in (copy / "runs").iterdir() if p.is_dir())
    run.rename(run.parent / "renamed")

    assert module.digest_of(copy) != before, (
        "renaming a run left the digest unchanged, so a proof naming it says "
        "nothing about which artefact was opened"
    )


def test_the_engine_never_writes_a_consumer_proof(described):
    """THE PROPERTY THAT KEEPS THIS FROM BEING SELF-CERTIFICATION.

    The producer publishes the artefact and its identity. Everything about who
    opened it is written by whoever opened it, and there is nothing in this
    repository that can write it -- which is why the description says how a
    consumer proves it rather than that one has.
    """
    text = json.dumps(described)

    assert "consumer_proof" not in text
    assert "proven" not in text

    source = (ROOT / "tools" / "reference-bundle.py").read_text(encoding="utf-8")
    assert 'consumer": "proven' not in source
    assert "consumer_proof" not in source.replace(
        "consumer, consumer_version", ""
    ).replace("record consumer", "")


def test_it_is_not_presented_as_tenant_evidence(described):
    """A compatibility artefact travelling as if it were an observation is the
    same defect as a fixture doing it, one boundary further out."""
    assert "fabricated" in described["purpose"]

    for document in REFERENCE.rglob("*-spo-collector.json"):
        provenance = json.loads(document.read_text(encoding="utf-8"))["provenance"]
        assert provenance.get("tenant", {}).get("host", "").startswith("contoso"), (
            f"{document.name} names something that is not the fabricated tenant"
        )
