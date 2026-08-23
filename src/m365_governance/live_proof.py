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

#: THE FIVE THINGS A RUN CAN PROVE, and they are not one thing.
#:
#: `full` in the published contract means "a real read produced real evidence".
#: It never claimed the rest, and a presentation layer rendered it as READ FROM
#: A TENANT, END TO END -- which is a wider sentence than the value supports,
#: made by a layer that may explain a contract value and never redefine it.
#:
#: Naming the stages separately is what makes that inflation impossible to
#: repeat: a consumer asking "was this proved end to end" now has a field to
#: read instead of a word to interpret.
STAGES = (
    # The Microsoft surface was actually read.
    "acquisition",
    # The document this collector promises was produced from that read.
    "evidence",
    # Rules actually consumed that evidence and decided something.
    "assessment",
    # The canonical artefact was produced from it.
    "bundle",
    # An independent consumer opened that artefact.
    "consumer",
)

#: What a stage may be, and the two that are not failures.
#:
#: `refused` is a typed refusal: a 403, a `not-supported`. It proves the FAILURE
#: path and never the positive one, and collapsing it into `not-attempted`
#: would throw away a real observation.
#:
#: `not-applicable` is the stage not existing for this capability. A collector
#: that feeds no rule has no assessment to prove, and demanding one would make
#: `vertical path proven` unreachable for a capability that is complete.
STAGE_STATES = ("proven", "refused", "attempted", "not-attempted", "not-applicable")

#: The ladder a capability climbs, weakest first. DERIVED FROM THE STAGES, so
#: it cannot say more than the stages under it.
LADDER = (
    "not-live-tested",
    "acquisition-attempted",
    "positive-acquisition-observed",
    "vertical-path-proven",
)


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

    THE STAGES ARE FILLED FROM WHAT WAS OBSERVED, NEVER FROM WHAT THE COMMAND
    WAS ASKED TO DO. `collect` acquires and writes evidence and does nothing
    else, so that is all it may claim; `run` evaluates and can bundle, and
    upgrades the record afterwards from what those steps actually produced.
    The first version of this emitted no stages at all, which would have left
    the authorized run producing a record that could not feed the ladder the
    whole registry exists to derive -- the field governing the derivation
    filled in by hand, which is the shape this replaced.
    """
    written = len(getattr(outcome, "written", ()) or ())
    state = str(getattr(outcome, "state", "") or "")

    # A refusal is a real observation and is not an acquisition. Anything that
    # produced no document acquired nothing, whatever it returned.
    if state in ("refused", "permission-denied", "not-supported"):
        acquisition = "refused"
    elif written:
        acquisition = "proven"
    else:
        acquisition = "attempted"

    stages = {
        "acquisition": acquisition,
        "evidence": "proven" if written else "not-attempted",
        # `collect` runs no rule. A capability that feeds none has no
        # assessment to prove; one that does has an unattempted stage, and
        # saying so is what stops a collection being read as a whole vertical.
        "assessment": (
            "not-applicable" if not SLICE_FEEDS_RULES(collector) else "not-attempted"
        ),
        "bundle": "not-attempted",
        "consumer": "not-attempted",
    }

    return {
        "stages": stages,
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


def stages(collector: str) -> dict[str, str]:
    """Every stage for one collector, as the strongest thing any record proves.

    A stage nobody wrote about is `not-attempted`. THE ABSENCE OF A RECORD IS
    THE ANSWER: `bundle` and `consumer` are `not-attempted` for every migrated
    record because the matrix those records came from does not mention either,
    and a stage cannot be raised because it probably happened.
    """
    found = {stage: "not-attempted" for stage in STAGES}
    for record in records(collector):
        for stage, state in (record.get("stages") or {}).items():
            if stage not in STAGES or state not in STAGE_STATES:
                continue
            if _PICK.index(state) < _PICK.index(found[stage]):
                found[stage] = state
    return found


#: WHICH VALUE WINS WHEN RECORDS DISAGREE, and it is not the vocabulary order.
#:
#: `not-applicable` is not a weak stage. It is a statement that the stage does
#: not exist for this capability, and it has to beat the `not-attempted` this
#: function starts from -- otherwise the default silently overrides what a
#: record actually says, which is how `agents` and `licensing` came back
#: claiming an assessment was merely unattempted when the record said there is
#: no assessment to attempt.
_PICK = ("proven", "refused", "attempted", "not-applicable", "not-attempted")


def proof_state(collector: str) -> str:
    """Where this capability stands, derived from its stages and nothing else.

    `vertical-path-proven` requires every APPLICABLE stage proven, so a
    capability that feeds no rule reaches it without pretending an assessment
    happened, and a capability that feeds one does not reach it by skipping.
    """
    if not records(collector):
        return "not-live-tested"

    by_stage = stages(collector)
    if by_stage["acquisition"] != "proven":
        # A refusal, a provider-only read, or an attempt that produced nothing
        # positive. Real, recorded, and not an acquisition.
        return "acquisition-attempted"

    applicable = [state for state in by_stage.values() if state != "not-applicable"]
    if all(state == "proven" for state in applicable):
        return "vertical-path-proven"
    return "positive-acquisition-observed"


def population() -> dict[str, list[str]]:
    """Every capability, grouped by where it stands. The site renders this.

    Returned as the collectors themselves rather than as counts, because a
    figure whose members cannot be listed is a figure nobody can check.
    """
    from m365_governance.collecting import SLICES

    grouped: dict[str, list[str]] = {rung: [] for rung in LADDER}
    for name in sorted(SLICES):
        grouped[proof_state(name)].append(name)
    return grouped


def SLICE_FEEDS_RULES(collector: str) -> bool:
    """Whether any rule reads this collector's evidence.

    Read from the capability manifest rather than kept beside it: a second list
    of which collectors feed rules is a second thing to keep true, and the
    first to go stale.
    """
    from m365_governance.collecting import SLICES

    chosen = SLICES.get(collector)
    return bool(chosen and chosen.produces_findings)


def upgrade_after_a_run(draft: dict, *, evaluated: bool, bundled: bool) -> dict:
    """What `run` may add to a `collect` record, from what it can attribute.

    `assessment` reaches `attempted` and never `proven`. A rule decides about a
    RESOURCE and evidence is composed by resource before evaluation, so a
    result cannot be traced back to the collector whose fact it read; the
    evidence's own provenance does not close it either, because eleven
    SharePoint slices all publish `spo-collector`. A person confirms from the
    report whether a rule decided anything from this slice's facts.

    Recorded rather than worked around: `charter/IDEAS.md` carries it as the
    same shape the Conditional Access family had, which is evidence not
    carrying what a downstream question needs.
    """
    stages = dict(draft.get("stages") or {})
    if evaluated and stages.get("assessment") == "not-attempted":
        stages["assessment"] = "attempted"
    if bundled:
        stages["bundle"] = "proven"
    return {**draft, "stages": stages}
