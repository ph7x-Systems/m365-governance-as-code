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


# ---------------------------------------------------------------------------
# two axes, one register
# ---------------------------------------------------------------------------
#
# THE RECORDS BELOW FEED TWO DIFFERENT QUESTIONS, AND THEY ARE NOT THE SAME
# QUESTION. One register is right -- a single run establishes facts on both --
# but reading one axis as the other is how a capability gets described as
# proved when half of what that word could mean was never attempted.
#
#     Live Validation        how well the ACQUISITION was validated against
#                            Microsoft 365. Derived by `established_state`,
#                            published as `live_validation_state`, and its
#                            vocabulary is `ESTABLISHES` below: none,
#                            negative-only, provider-only, partial, full.
#                            `docs/LIVE-VALIDATION.md` owns what those mean.
#
#     Product Path Assurance how far that capability has been proved THROUGH
#                            THIS PRODUCT. Derived by `proof_state`, published
#                            as `proof.state`, and its vocabulary is `LADDER`:
#                            not-live-tested, acquisition-attempted,
#                            positive-acquisition-observed,
#                            vertical-path-proven.
#
# NEITHER DERIVES FROM THE OTHER, and a capability can sit high on one and low
# on the other in both directions. A collector whose acquisition was compared
# against a second authoritative surface and whose divergences were
# investigated is strong on the first axis and still has nobody who has opened
# its bundle. A slice whose evidence, assessment and bundle all ran from one
# unremarkable read is high on the second and has never had its representation
# checked against what the fields are claimed to mean.
#
# The word `proof` on its own means neither, and this module uses it for the
# REGISTER -- the records -- rather than for either conclusion drawn from them.

#: Stages that cannot be proven on their own, and what each one stands on.
#:
#: A DEPENDENCY, NOT A PREFERENCE. Nothing can open a bundle that was never
#: produced; no bundle can hold an assessment that never ran; no assessment can
#: read evidence that was never written. These are facts about the pipeline,
#: and a record claiming otherwise is describing something that did not happen.
STANDS_ON = {
    "evidence": "acquisition",
    "assessment": "evidence",
    "bundle": "evidence",
    "consumer": "bundle",
}


#: What a `consumer: proven` claim has to carry, and why each field is there.
#:
#: THE STAGE THIS SOFTWARE CANNOT RAISE. `upgrade_after_a_run` moves
#: `assessment` and `bundle` and deliberately never touches `consumer`:
#: somebody independent opening the artefact is the one stage a program
#: certifying it would be certifying itself. So the claim is written from
#: outside, and a claim written from outside has to say who wrote it.
#:
#: DELIBERATELY FIVE FIELDS. A taxonomy invented before there is a second
#: consumer would be a shape guessed rather than observed. These are the ones
#: without which `proven` cannot answer a question somebody will ask.
CONSUMER_PROOF = (
    # WHICH consumer, by whatever name it calls itself. `consumer: proven`
    # with no name is a sentence that stops answering "by whom?" the moment
    # the person who wrote it has moved on.
    #
    # NOT AN ENUMERATION, AND NOT BY OVERSIGHT. This engine defines the SHAPE
    # of the claim and never who is allowed to make it: a list of permitted
    # consumers here would put one product's roster inside another's contract,
    # and a consumer this repository has never heard of makes the same claim
    # on the same terms.
    "consumer",
    # A consumer is a moving product. The version that opened it is the
    # version the claim is about, and a later one may not.
    "consumer_version",
    # WHAT KIND of independence, because two very different claims fit the
    # same word and only one of them is ours to make.
    "independence",
    # WHEN, so that a claim can be aged rather than believed indefinitely.
    "observed_at",
    # WHICH ARTEFACT, by digest. Without it a proof that the consumer opened
    # bundle B can be read as proving the capability derived from bundle A.
    "artifact_digest",
)

#: How independent the consumer was, and the two are not degrees of one thing.
#:
#: `separate-consumer` is what this product can establish about itself: a
#: different program, run outside the process that produced the artefact,
#: opened it and read it correctly. It proves the artefact is consumable and
#: that the producer did not certify itself.
#:
#: `external` is a claim about an ORGANISATION rather than a process, and
#: nothing in this repository can produce it. It exists here so that the day
#: somebody can, the earlier records do not silently acquire a meaning nobody
#: gave them: a value written now says exactly what was true now.
INDEPENDENCE = ("separate-consumer", "external")


def incoherent(collector: str) -> list[str]:
    """Stages claimed as proven that nothing underneath them supports.

    THE TEMPTATION THIS REFUSES IS PROMOTION, AND IT COMES FROM BOTH ENDS.

    Upward: `consumer` proven must never raise `bundle`, because the whole
    number this product is answerable for is derived from these stages and an
    inference is exactly where a derived number starts being a claim. Nothing
    here promotes; `stages()` takes the strongest thing a record ACTUALLY says
    and defaults to `not-attempted`.

    Downward is the hole this closes. A record could always say `consumer:
    proven` beside `bundle: not-attempted`, and it was accepted in silence: the
    contradiction quietly lowered the capability's state rather than being
    reported, so the register held a sentence describing something impossible
    and nobody was told. A weaker answer is not the same as a correct one, and
    a register that absorbs its own contradictions is the second authority this
    programme spends its effort removing.

    `not-applicable` is not a gap. A stage that does not exist for a capability
    cannot be the thing a later stage failed to stand on: what it stands on is
    whatever the missing stage itself stood on, so the chain is walked through
    it rather than broken by it.
    """
    by_stage = stages(collector)
    broken = []
    for stage, beneath in STANDS_ON.items():
        if by_stage.get(stage) != "proven":
            continue
        while by_stage.get(beneath) == "not-applicable":
            beneath = STANDS_ON.get(beneath, "")
            if not beneath:
                break
        if beneath and by_stage.get(beneath) != "proven":
            broken.append(
                f"{collector}: `{stage}` is recorded as proven while "
                f"`{beneath}` is `{by_stage.get(beneath)}`. Nothing can prove "
                f"a stage that stands on one that was never reached."
            )

    broken.extend(_consumer_problems(collector))
    return broken


def _consumer_problems(collector: str) -> list[str]:
    """Whether a `consumer: proven` claim carries the proof it needs.

    THIS IS THE ONE STAGE WRITTEN FROM OUTSIDE, so it is the one stage whose
    record has to identify its author. Every other stage is raised by a run
    this engine performed and can be traced through the run's own outcome; a
    consumer claim arrives as a sentence, and a sentence with no author stops
    answering "by whom?" the moment the person who wrote it moves on.

    AND THE DIGEST HAS TO BE THE RIGHT ARTEFACT'S. A record may hold a bundle
    stage proven for one artefact and a consumer proof mentioning another; read
    together they say a consumer opened THIS capability's bundle, and nothing
    checked that. It is the same shape as a rule reading a fact from the wrong
    resource, and it is caught the same way: by comparing the two identifiers
    rather than trusting that they were about the same thing.
    """
    problems = []
    for record in records(collector):
        stages_here = record.get("stages") or {}
        if stages_here.get("consumer") != "proven":
            continue

        proof = record.get("consumer_proof")
        if not isinstance(proof, dict):
            problems.append(
                f"{collector}: `consumer` is recorded as proven with no "
                "`consumer_proof`. This is the stage no run can raise, so a "
                "claim with no author is a claim nobody can check."
            )
            continue

        for field in CONSUMER_PROOF:
            if not proof.get(field):
                problems.append(
                    f"{collector}: `consumer_proof` does not say `{field}`."
                )

        independence = proof.get("independence")
        if independence and independence not in INDEPENDENCE:
            problems.append(
                f"{collector}: `consumer_proof.independence` is "
                f"`{independence}`, which is not one of {list(INDEPENDENCE)}. "
                "A word invented here would let a claim about a separate "
                "process be read as a claim about a separate organisation."
            )

        opened = proof.get("artifact_digest")
        produced = record.get("artifact_digest")
        if opened and produced and opened != produced:
            problems.append(
                f"{collector}: the consumer opened `{opened}` and the bundle "
                f"this record proves is `{produced}`. A proof about one "
                "artefact does not establish anything about another."
            )
        elif opened and not produced:
            problems.append(
                f"{collector}: `consumer_proof` names an artefact and the "
                "record does not say which artefact its bundle stage "
                "produced, so the two cannot be shown to be the same one."
            )
    return problems


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
