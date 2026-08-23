"""Where a collector's live state comes from, and the direction it comes in.

**A live state used to be a sentence somebody wrote beside a collector.** It
travelled from there into the capability manifest, out through the site's
generator, and onto a public page as *read from a tenant, end to end*. Nothing
between the sentence and the page checked that a tenant had ever been read.
That is not a hypothetical: `docs/COLLECTOR-LIVE-MATRIX.md` said `not observed`
for a collector whose own source claimed a defect had been found by provoking
the state in a directory, and both had been true-looking for weeks.

So the field stops being declared and starts being derived:

    real execution  ->  sanitized proof record  ->  validated  ->  live state

and never the other way. **A collector with no record is `none`**, whatever
anybody believes about it, and deleting a record lowers the state that rests on
it. That is the property worth having: the public claim is a consequence of the
proof, rather than the proof being a consequence of the claim.

NO TENANT DATA IS INVOLVED IN ANY OF THIS. A record carries a method, a date,
an identity KIND, a population as a count or a shape, a result, limitations and
versions. It carries no hostname, no tenant identifier, no principal name, no
resource name and no evidence content, and `tests/test_live_proof.py` refuses a
record that does.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REGISTRY = Path(__file__).parent / "data" / "live-proof.json"

#: The one provenance that may not grow. These records transcribe what was
#: written down contemporaneously, before this registry existed; they are
#: honest and they are weaker than a record an execution emitted, because the
#: artefacts are gone and several fields were never captured. Closing the set
#: is what stops the forbidden direction from being available again: from here
#: on, the only way to raise a state is to run something.
MIGRATED = "migrated-from-the-collector-live-matrix"
EMITTED = "emitted-by-a-run"

PROVENANCES = (MIGRATED, EMITTED)

#: What a record may claim, weakest first. A collector's state is the strongest
#: claim among its valid records; with no record it is the absence of all of
#: them.
ESTABLISHES = ("negative_only", "provider_only", "partial", "full")


@lru_cache(maxsize=1)
def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def records(collector: str | None = None) -> list[dict]:
    """Every proof record, or every record for one collector."""
    found = _registry()["records"]
    if collector is None:
        return list(found)
    return [r for r in found if r.get("collector") == collector]


def established_state(collector: str) -> str:
    """The live state this collector's records support. `none` if they do not.

    THE ABSENCE OF A RECORD IS NOT AN OMISSION TO BE FILLED IN LATER. It is the
    answer: nothing has been proved about this collector against a directory,
    and the product says so rather than carrying a value somebody meant to
    check.
    """
    claims = [r.get("establishes") for r in records(collector)]
    known = [c for c in claims if c in ESTABLISHES]
    if not known:
        return "none"
    return max(known, key=ESTABLISHES.index)


def draft_from_run(outcome, *, collector: str, acquisition_method: str) -> dict:
    """The record a real execution leaves behind, sanitized at the source.

    THIS IS THE ONLY WAY A STATE MAY RISE FROM NOW ON. The migrated set is
    closed, so a collector's live state can only be raised by running it and
    keeping what the run produced. What is kept is deliberately thin: enough to
    prove an execution happened and what it covered, and nothing that says
    whose directory it was.

    `establishes` is left for a person to set, and that is not an oversight. A
    run proves an acquisition; it does not prove that the interpretation of
    what came back is correct, and `docs/LIVE-VALIDATION.md` names the steps
    between those two. A collector that wrote its own `full` at the end of a
    successful call would be back where this started -- a claim produced by the
    thing it is a claim about.
    """
    written = len(getattr(outcome, "written", ()) or ())
    return {
        "collector": collector,
        "acquisition_method": acquisition_method,
        "observed_at": getattr(outcome, "started_at", None),
        "identity_kind": "not recorded: set it to the KIND, never the identity",
        # A count, never the things counted. The documents themselves are
        # tenant evidence and do not leave the operator's machine.
        "population": f"{written} documents",
        "coverage": "",
        "result": getattr(outcome, "state", None) or "",
        "limitations": [],
        "contract_versions": {},
        "engine_version": "",
        # Continuity with what was observed, and nothing more. When the
        # artefact is deleted under the tenant-data rule, the disposition below
        # is what a reader has instead of the ability to check it.
        "artifact_digest": getattr(outcome, "digest", None),
        "artifact_disposition": "held by the operator; not committed",
        "establishes": None,
        "provenance": EMITTED,
    }
