"""One run, one folder, and nothing computed that a document does not already say.

WHAT THIS IS NOT. It is not a new format and it does not decide anything. Every
byte it writes is a document this engine already produces: the run document is
what `--format json` renders for a single run, the evidence is what `collect`
wrote, and the report is what `report` renders. All that was missing was a place
to put them together with a name, and the absence of that place is why nothing in
the world had ever produced a workspace the desktop product could open.

THE SHAPE IS NOT INVENTED HERE EITHER. It is the one `LocalWorkspaceStore`
already reads and already documents:

    <root>/
      runs/
        20260805T140211Z-c49faa42/
          run.json
          evidence/
          report.md
      manifest.json

Designing a second arrangement for the same files would create exactly the second
authority this programme spends its effort removing.

THE MANIFEST CARRIES POINTERS AND A VERSION AND NOTHING ELSE. Not when the run
was collected, not which engine collected it, not a digest over it: all three live
in the run document, and a second copy of a fact is a second place for it to be
wrong. `verify` reads the document.

THE FOLDER NAME IS DERIVED, NEVER STAMPED. The timestamp is the run's own
`provenance.collected_at` and the digest is over the run document's bytes, so the
arrangement asserts nothing the documents do not. Two runs collected in the same
second are separated by their digests, which is the reason the name has two
halves.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .reporting import to_html, to_json, to_markdown
from .results import Run

#: The bundle's own version, and the only thing here that is not a pointer. It
#: is a plain string rather than a published schema URL: naming an arrangement
#: of existing documents does not need a new contract, and minting one would add
#: a surface rather than name an output.
VERSION = "1.0.0"

_SUFFIX = {"json": "json", "html": "html", "markdown": "md"}
_RENDER = {"json": to_json, "html": to_html, "markdown": to_markdown}


class BundleError(Exception):
    """The bundle could not be written, with the reason a caller can act on."""


def _stamp(run: Run) -> str:
    """`2026-08-05T14:02:11Z` as `20260805T140211Z`, from the run itself."""
    collected = (run.provenance or {}).get("collected_at")
    if not collected:
        raise BundleError(
            "a run carries no provenance.collected_at, so its folder cannot be "
            "named from the document. The arrangement does not invent a time."
        )
    return re.sub(r"[-:]", "", str(collected))


def _identity(run: Run) -> str | None:
    resource = run.resource or {}
    return resource.get("native_id") if isinstance(resource, dict) else None


def write(
    root: Path,
    runs: list[Run],
    documents: list[dict],
    fmt: str = "markdown",
    run_set: dict | None = None,
) -> Path:
    """Write one folder per run under `root`, and return `root`.

    `documents` are the evidence documents as they were collected. Each run
    receives the ones describing its own resource, matched on `resource.native_id`
    because that is the identity both halves already carry. A document that
    matches nothing is not dropped silently: it goes to `evidence/` at the root,
    where it is still readable and still says what it always said.
    """
    if fmt not in _RENDER:
        raise BundleError(f"unknown report format {fmt!r}")

    root = Path(root)
    (root / "runs").mkdir(parents=True, exist_ok=True)

    by_resource: dict[str | None, list[dict]] = {}
    for document in documents:
        resource = document.get("resource") or {}
        key = resource.get("native_id") if isinstance(resource, dict) else None
        by_resource.setdefault(key, []).append(document)

    claimed: set[int] = set()
    written: list[str] = []

    for run in runs:
        body = to_json(run).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()[:8]
        folder = root / "runs" / f"{_stamp(run)}-{digest}"
        folder.mkdir(parents=True, exist_ok=True)

        (folder / "run.json").write_bytes(body)

        identity = _identity(run)
        matched = by_resource.get(identity, [])
        if matched:
            (folder / "evidence").mkdir(exist_ok=True)
            for index, document in enumerate(matched, start=1):
                claimed.add(id(document))
                name = f"{index:02d}-{_collector(document)}.json"
                (folder / "evidence" / name).write_text(
                    json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

        (folder / f"report.{_SUFFIX[fmt]}").write_text(
            _RENDER[fmt](run), encoding="utf-8"
        )
        written.append(f"runs/{folder.name}")

    # EVIDENCE THAT MATCHED NO RUN IS STILL EVIDENCE. A collection that produced
    # a document for a resource no rule spoke to is a fact about coverage, and
    # discarding it here would make the bundle quieter than the run was.
    orphans = [d for d in documents if id(d) not in claimed]
    if orphans:
        (root / "evidence").mkdir(exist_ok=True)
        for index, document in enumerate(orphans, start=1):
            (root / "evidence" / f"{index:02d}-{_collector(document)}.json").write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    # THE TENANT-SCALE VIEW, BESIDE THE RUNS RATHER THAN DERIVED FROM THEM.
    #
    # A bundle carried runs and nothing else, so a consumer opening one had no
    # way to show a SERVICE that collected evidence and concluded nothing: it
    # appears in no run at all, because there is no run to appear in. Deriving
    # it on the other side would make the consumer a second authority on what a
    # service is and what an area is, and that is the first thing it would get
    # wrong.
    #
    # Written only when the caller has one. `evaluate` over a directory has a
    # run set; a caller that does not is not made to invent one.
    if run_set is not None:
        (root / "run-set.json").write_text(
            json.dumps(run_set, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    # NOT IN `runs`. That list is what a consumer walks to find run documents,
    # and a run set is not a run: putting it there would have every reader
    # trying to parse the tenant-scale view against the run contract.
    manifest = {"bundle": VERSION, "runs": sorted(written)}
    if orphans:
        manifest["evidence"] = "evidence"

    def _write(document: dict) -> None:
        (root / "manifest.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # THE IDENTITY TRAVELS INSIDE THE ARTEFACT, and the consumer reads it from
    # the artefact it opened rather than being told it by whoever handed the
    # bundle over. A consumer that repeats an identifier it was given has
    # confirmed what somebody said; one that reads it from the bundle has
    # confirmed what the bundle says about itself.
    #
    # NOT A SECOND IMPLEMENTATION IN THE CONSUMER EITHER. A consumer computing
    # the hash independently would be a stronger claim and a duplicated
    # algorithm, and two implementations give two answers for one artefact.
    # What this establishes is precisely: the consumer opened the artefact that
    # identified itself as the bundle the producer recorded. Nothing about
    # cryptographic verification by the consumer, which is a different claim
    # and is not made anywhere.
    #
    # Written twice because the digest covers the manifest with this field
    # removed: the file has to exist before the tree can be hashed, and adding
    # the value afterwards cannot change what was hashed.
    _write(manifest)
    manifest["bundle_digest"] = digest_of(root)
    _write(manifest)

    return root


#: Keys by which a document declares its own identity.
#:
#: A FILE THAT CARRIES THE IDENTITY DOES NOT CARRY IT INTO THE IDENTITY. A
#: manifest holding `bundle_digest` is inside the tree the digest covers, so
#: hashing it whole asks for a fixed point: the value depends on a file whose
#: contents depend on the value.
#:
#: ONE RULE AND NOT A LIST OF EXCEPTED FILES. Excluding `manifest.json`
#: entirely would leave the run list and the bundle version outside the
#: identity, so a bundle could lose a run and keep its digest. Excluding the
#: FIELD keeps everything else in.
SELF_DECLARED = ("bundle_digest", "digest")


def _for_digest(path: Path) -> bytes:
    """One file's bytes as the identity sees them."""
    raw = path.read_bytes()
    if path.suffix != ".json":
        return raw
    try:
        document = json.loads(raw)
    except ValueError:
        # Not readable as JSON is a fact about the file, and the identity
        # covers it as it stands rather than skipping it.
        return raw
    if not isinstance(document, dict):
        return raw
    # UNCONDITIONALLY, AND THAT IS THE WHOLE OF IT. Applying this only when the
    # field is present makes the same document hash two different ways: without
    # the field it entered as raw bytes, with it as canonical JSON, so the
    # digest a manifest declared never equalled the digest of the tree holding
    # that manifest. The rule cannot depend on the value it exists to leave out.
    stripped = {k: v for k, v in document.items() if k not in SELF_DECLARED}
    return json.dumps(stripped, sort_keys=True, separators=(",", ":")).encode()


def digest_of(root: Path) -> str:
    """One digest over a whole bundle, paths included.

    WHY A BUNDLE NEEDS AN IDENTITY AT ALL. `bundle: proven` says an artefact
    was produced and says nothing about WHICH, so the stage above it -- a
    consumer opening one -- can never demonstrate it opened the same thing.
    Two true sentences that cannot be shown to be about one artefact establish
    nothing together.

    OVER THE PATHS AS WELL AS THE BYTES. A digest of concatenated contents is
    identical for a bundle whose files were renamed, and a consumer proving it
    opened `runs/a` when the artefact now calls it `runs/b` has proved nothing
    about what anybody holds.

    THE ARTEFACT ENDS WHERE THE PRODUCER CLOSES IT. Anything a consumer writes
    beside the runs afterwards -- an index, a workspace file -- is that
    consumer's local state and was never part of what it opened. So the digest
    is computed once, by the producer, at the moment the bundle is finished.
    """
    parts = []
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            parts.append(str(path.relative_to(root)).replace("\\", "/"))
            parts.append(hashlib.sha256(_for_digest(path)).hexdigest())
    return "sha256:" + hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _collector(document: dict) -> str:
    """The collector's name, for a filename that says where a document came from."""
    provenance = document.get("provenance") or {}
    name = provenance.get("collector") if isinstance(provenance, dict) else None
    slug = re.sub(r"[^a-z0-9-]+", "-", str(name or "evidence").lower()).strip("-")
    return slug or "evidence"
