"""One folder per run, and nothing in it this engine did not already produce.

WHY THESE EXIST AT ALL. The run documents lived only in memory: computed,
wrapped in a run set, rendered and dropped. Nothing had ever written one to a
file, which is why nothing in the world had produced a folder a consumer could
open. These tests hold the arrangement, and hold it against the rule that makes
it trustworthy: **the folder asserts nothing the documents do not already say.**
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m365_governance import bundling
from m365_governance.reporting import to_json
from m365_governance.resources import packaged

FIXTURES = packaged("fixtures") / "sharepoint"


def _runs(tmp_path: Path, names: tuple[str, ...]):
    """Evidence in, runs and documents out, through the engine's own path."""
    import types

    from m365_governance.cli import _evaluate_all

    evidence = tmp_path / "evidence-in"
    evidence.mkdir()
    for name in names:
        (evidence / name).write_bytes((FIXTURES / name).read_bytes())

    args = types.SimpleNamespace(
        evidence=evidence, rules=None, profile=None, format="markdown"
    )
    return _evaluate_all(args)


def test_one_folder_per_run_each_with_its_document(tmp_path: Path) -> None:
    runs, documents = _runs(
        tmp_path, ("list-over-limit.json", "site-activity-archived.json")
    )
    root = bundling.write(tmp_path / "bundle", runs, documents)

    folders = sorted(p for p in (root / "runs").iterdir() if p.is_dir())
    assert len(folders) == len(runs)
    for folder in folders:
        assert (folder / "run.json").is_file()
        assert (folder / "report.md").is_file()


def test_the_run_document_is_the_engine_s_own_bytes(tmp_path: Path) -> None:
    """Not a re-serialisation. The bundle carries what `--format json` renders."""
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))
    root = bundling.write(tmp_path / "bundle", runs, documents)

    folder = next(p for p in (root / "runs").iterdir() if p.is_dir())
    assert (folder / "run.json").read_bytes() == to_json(runs[0]).encode("utf-8")


def test_the_folder_is_named_from_the_document_and_not_from_the_clock(
    tmp_path: Path,
) -> None:
    """The timestamp is the run's own `collected_at`, so a bundle written twice
    from the same documents produces the same names. A name that moved with the
    clock would be a fact the arrangement invented."""
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))

    first = bundling.write(tmp_path / "a", runs, documents)
    second = bundling.write(tmp_path / "b", runs, documents)

    assert [p.name for p in sorted((first / "runs").iterdir())] == [
        p.name for p in sorted((second / "runs").iterdir())
    ]

    collected = runs[0].provenance["collected_at"]
    stamp = collected.replace("-", "").replace(":", "")
    assert next(iter((first / "runs").iterdir())).name.startswith(stamp)


def test_two_runs_collected_in_the_same_second_do_not_collide(
    tmp_path: Path,
) -> None:
    """Which is why the name has two halves."""
    runs, documents = _runs(
        tmp_path, ("list-over-limit.json", "list-class-unknown.json")
    )
    stamps = {r.provenance["collected_at"] for r in runs}
    assert len(stamps) == 1, "the fixture no longer shares a timestamp"

    root = bundling.write(tmp_path / "bundle", runs, documents)
    assert len(list((root / "runs").iterdir())) == len(runs)


def test_each_run_carries_the_evidence_it_was_decided_from(tmp_path: Path) -> None:
    runs, documents = _runs(
        tmp_path, ("list-over-limit.json", "site-activity-archived.json")
    )
    root = bundling.write(tmp_path / "bundle", runs, documents)

    for folder in (p for p in (root / "runs").iterdir() if p.is_dir()):
        run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        carried = list((folder / "evidence").glob("*.json"))
        assert carried, f"{folder.name} carries no evidence"
        for path in carried:
            document = json.loads(path.read_text(encoding="utf-8"))
            assert document["resource"]["native_id"] == run["resource"]["native_id"]


def test_evidence_that_matched_no_run_is_still_written(tmp_path: Path) -> None:
    """A document for a resource no rule spoke to is a fact about coverage.
    Dropping it would make the bundle quieter than the run was."""
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))
    orphan = dict(documents[0])
    orphan["resource"] = dict(
        orphan["resource"], native_id="contoso,list,nothing-asked"
    )

    root = bundling.write(tmp_path / "bundle", runs, [*documents, orphan])

    assert list((root / "evidence").glob("*.json")), "the orphan was dropped"
    assert json.loads((root / "manifest.json").read_text(encoding="utf-8"))["evidence"]


def test_the_manifest_carries_pointers_and_a_version_and_nothing_else(
    tmp_path: Path,
) -> None:
    """Not `created_at`, not `engine_version`, not a digest: each of those lives
    inside a document, and a second copy of a fact is a second place for it to be
    wrong."""
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))
    root = bundling.write(tmp_path / "bundle", runs, documents)

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"] == bundling.VERSION
    assert manifest["runs"] == [
        f"runs/{p.name}" for p in sorted((root / "runs").iterdir()) if p.is_dir()
    ]
    for forbidden in ("created_at", "engine_version", "digest", "generated"):
        assert forbidden not in manifest


@pytest.mark.parametrize("fmt,suffix", [("json", "json"), ("html", "html")])
def test_the_report_is_written_in_the_format_asked_for(
    tmp_path: Path, fmt: str, suffix: str
) -> None:
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))
    root = bundling.write(tmp_path / "bundle", runs, documents, fmt)

    folder = next(p for p in (root / "runs").iterdir() if p.is_dir())
    assert (folder / f"report.{suffix}").is_file()


def test_an_unknown_format_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))
    with pytest.raises(bundling.BundleError, match="unknown report format"):
        bundling.write(tmp_path / "bundle", runs, documents, "pdf")


def test_a_run_with_no_collection_time_is_refused_by_name(tmp_path: Path) -> None:
    """The arrangement does not invent a time. A run that cannot name its own
    moment cannot be filed, and saying so beats filing it under now."""
    runs, documents = _runs(tmp_path, ("list-over-limit.json",))
    runs[0].provenance.pop("collected_at")

    with pytest.raises(bundling.BundleError, match="provenance.collected_at"):
        bundling.write(tmp_path / "bundle", runs, documents)
