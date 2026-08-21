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
    root: Path, runs: list[Run], documents: list[dict], fmt: str = "markdown"
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

    manifest = {"bundle": VERSION, "runs": sorted(written)}
    if orphans:
        manifest["evidence"] = "evidence"
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return root


def _collector(document: dict) -> str:
    """The collector's name, for a filename that says where a document came from."""
    provenance = document.get("provenance") or {}
    name = provenance.get("collector") if isinstance(provenance, dict) else None
    slug = re.sub(r"[^a-z0-9-]+", "-", str(name or "evidence").lower()).strip("-")
    return slug or "evidence"
