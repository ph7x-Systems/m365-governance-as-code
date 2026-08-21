"""What this engine can do, in one document a consumer can read.

Every fact here already exists somewhere: the slice registry knows the
collectors, the rule files know the rules and their basis, the schema registry
knows the contracts, and each slice now carries what a real tenant has
established about it. Nothing joined them, so anybody who wanted the whole
picture rebuilt it by hand — and a hand-built copy of a fact this repository
owns is a second authority that goes stale in silence.

**IT IS DERIVED AND NEVER WRITTEN DOWN.** There is no file to refresh and no
generator to forget: the manifest is computed from the objects it describes
every time it is asked for, so it cannot drift from them. That is the whole
design. A generated artefact committed to the tree would need a gate to prove
it current, and the gate would be one more thing to be red on a Friday.

WHAT IT IS NOT. Not state, not a queue, not a roadmap. A capability is in here
because it is implemented and shipping; planned work has no entry, and a
capability whose live column says nobody has run it says exactly that rather
than being left out to look better.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from . import collecting, registry
from .loader import load_rules
from .resources import packaged

#: The contract this document declares. Consumers read `$schema` and validate.
CONTRACT = "capability-manifest"


def manifest(rules: Path | None = None) -> dict[str, Any]:
    """The whole picture, assembled from the parts that own each piece."""
    loaded = [r.data for r in load_rules(rules or packaged("rules"))]

    return {
        "$schema": registry.contract(CONTRACT),
        "engine_version": _version(),
        "contract_version": collecting._contract_version(),
        "capabilities": [
            _capability(chosen, loaded)
            for chosen in sorted(collecting.SLICES.values(), key=lambda s: s.name)
        ],
        "contracts": sorted(_contracts()),
        "rules": sorted((_rule(rule) for rule in loaded), key=lambda r: str(r["id"])),
    }


def _capability(
    chosen: collecting.Slice, rules: list[dict[str, Any]]
) -> dict[str, Any]:
    """One slice, and everything that is true of it.

    The rules are not declared on the slice and are not counted here either.
    They are derived, and the derivation matters: matching on workload and
    resource type alone answered "which rules could apply to a document of this
    shape", which for SharePoint is nearly all of them — the classification
    slice came back owning fifteen rules it says nothing about. A rule belongs
    to a slice when the slice produces the facts the rule requires, and the
    fixture the slice is already paired with is what says which those are.
    """
    document = _fixture(chosen)
    resource = document.get("resource", {})
    workload = str(resource.get("workload", ""))
    resource_type = str(resource.get("type", ""))
    # The union across every shape: a rule this collector can decide in one
    # of its branches is a rule it feeds.
    consuming = sorted(
        set().union(*(_decidable(rules, d) for d in _shapes(chosen)))
        if _shapes(chosen)
        else set()
    )

    return {
        "name": chosen.name,
        "describes": chosen.describes,
        "collector": {
            "kind": chosen.source,
            "mode": chosen.mode,
            "reads": list(chosen.reads),
            # Empty is a real answer and not an omission: least privilege is
            # recorded where a source establishes it, and invented nowhere.
            "permissions": list(chosen.permissions) or ["not-established"],
            # TWO FIELDS, ONE OWNER. `live_validation` is the sentence a
            # person reads and `live_validation_state` is the value a consumer
            # derives from; the sentence is rendered from the state plus the
            # slice's own note, so they cannot come to disagree. The field was
            # a free string, typed in the schema as any non-empty one, and
            # anything asking "can this question be answered from a real
            # tenant" had to interpret prose.
            "live_validation": chosen.live_sentence(),
            "live_validation_state": chosen.live.name.lower().replace("_", "-"),
            # Least privilege belongs in the composition, not only in the
            # documentation: an identity that reads sites and not the tenant
            # runs every collector where this is false, and the catalogue is
            # where a consumer sees which capabilities that leaves them
            # without.
            "needs_tenant_surface": chosen.needs_tenant,
        },
        "produces": {"workload": workload, "resource_type": resource_type},
        "consumed_by": consuming if chosen.produces_findings else [],
        # Named whenever no rule reads it, which is the price of the exception
        # to the twin rule. Without it, "no rule" reads as "nobody looked".
        "consumer": chosen.consumed_by,
    }


def _decidable(rules: list[dict[str, Any]], document: dict[str, Any]) -> set[str]:
    """The rules that can reach an answer from what this slice produces.

    **Established by running them, not by comparing paths.** The first version
    intersected each rule's declared evidence paths with the fixture's fact
    keys, and it under-reported: `owners.count` is resolved by the engine from
    an aggregate fact and exists as no literal key, so a rule that decides
    perfectly well looked unsupported. The engine already knows how to resolve
    a path; asking it is one authority, and reimplementing it here would be two.

    `unknown` is the answer that excludes: it means the rule applies to this
    shape of resource and could not decide from what this slice collected.
    """
    from .engine import evaluate
    from .results import Outcome

    if not document:
        return set()
    return {
        str(result.rule_id)
        for result in evaluate(rules, document).results
        if result.outcome is not Outcome.UNKNOWN
    }


def _fixture(chosen: collecting.Slice) -> dict[str, Any]:
    """The document this slice is already paired with.

    One place has to be right for the profile pairing test to pass, and this is
    it. A second declaration on the slice would be a second thing to keep true.
    """
    document = _named(chosen.shaped_like)
    if not document:
        # A SLICE WHOSE SHAPE DOES NOT RESOLVE USED TO PUBLISH AN EMPTY ONE.
        # The folders were listed by hand here, a third one was added under
        # `fixtures/`, and the catalogue answered `workload: ""` for licensing
        # rather than saying it could not find the document. An unresolvable
        # pairing is a registry defect and it says so here.
        raise ValueError(
            f"slice {chosen.name} is shaped like {chosen.shaped_like}, and no "
            f"fixture of that name exists under fixtures/"
        )
    return document


def _named(name: str) -> dict[str, Any]:
    """The fixture of that name, from whichever family holds it.

    Searched rather than listed: the folder list was written out twice, and a
    new family reached neither copy.
    """
    from .loader import load_json

    for path in sorted(packaged("fixtures").glob(f"*/{name}.json")):
        return load_json(path)
    return {}


def _shapes(chosen: collecting.Slice) -> list[dict[str, Any]]:
    """Every shape this slice can produce, primary first.

    A collector with a branch produces more than one shape, and asking one of
    them which rules it feeds answers for that branch alone.
    """
    documents = [_fixture(chosen)]
    documents += [_named(n) for n in chosen.also_shaped_like]
    return [d for d in documents if d]


def _rule(rule: dict[str, Any]) -> dict[str, Any]:
    """A rule as a consumer needs it: what it decides, and on what authority.

    The basis travels because an outcome without it is an opinion with a
    severity attached, and the limitations travel because a pass that does not
    say what it left unresolved is the most expensive kind of green.
    """
    basis = rule.get("basis") or {}
    limitations = rule.get("limitations") or {}
    return {
        "id": rule.get("id"),
        "title": rule.get("title"),
        "service": rule.get("service"),
        "resource_type": rule.get("resource_type"),
        "severity": (rule.get("severity") or {}).get("default"),
        "basis": {
            "type": basis.get("type"),
            # Carried because for a `convention` it is the whole authority.
            # That basis type has no sources by design -- it says the threshold
            # is ours -- and a manifest that showed an empty source list and
            # nothing else would make an honest rule look unsupported.
            "rationale": _text(basis.get("rationale")),
            "sources": [
                {"url": s.get("url"), "title": s.get("title")}
                for s in basis.get("sources") or []
            ],
        },
        "evidence_requirements": [
            r.get("path") for r in rule.get("evidence_requirements") or []
        ],
        "limitations": {
            "passes_without_resolving": limitations.get("passes_without_resolving"),
            "other": list(limitations.get("other") or []),
        },
    }


def _text(value: Any) -> str | None:
    """A YAML folded block as one line, or None where there is none."""
    return " ".join(str(value).split()) if value else None


#: How much a live state proves, so the weakest link in a question can be found
#: without comparing sentences.
_PROVES = {"none": 0, "negative-only": 1, "provider-only": 2, "full": 3}


def questions(rules: Path | None = None) -> dict[str, Any]:
    """What this engine can defensibly answer about a real tenant.

    `capabilities()` answers "what does this product touch". This answers the
    question somebody actually has, which is "what can it tell me", and the two
    are not the same document: a collector that reads four cmdlets and feeds no
    rule is infrastructure, and a rule whose collector has only ever been run
    against an empty surface is not an answer yet.

    "We have twenty rules" is a count of files. It says nothing about whether
    any of them can be decided from a tenant, which is the only claim worth
    publishing. Each entry here carries the four things that make the verdict
    checkable rather than asserted: what evidence decides it, whether the
    collector that feeds it produces that evidence, what permission the
    collection rests on, and what a run against a real tenant has established
    about the path underneath.

    NOTHING IS MAINTAINED BY HAND. The join is `consumed_by`, which each slice
    already declares; the evidence paths are the rule's own; the availability
    is resolved against the fixtures that define each shape the collector
    writes. A second table would be a fifth place to forget.
    """
    document = manifest(rules)
    by_rule: dict[str, list[str]] = {}
    for capability in document["capabilities"]:
        for rule_id in capability["consumed_by"]:
            by_rule.setdefault(rule_id, []).append(capability["name"])
    catalogue = {c["name"]: c for c in document["capabilities"]}

    out = []
    for rule in document["rules"]:
        sources = sorted(by_rule.get(rule["id"], ()))
        paths = rule["evidence_requirements"]
        if not sources:
            # A rule no collector feeds is debt, and it says so rather than
            # being left out of the count.
            out.append(
                {
                    "id": rule["id"],
                    "question": rule["title"],
                    "answerable": "no",
                    "because": "no collector produces the evidence this rule needs",
                    "evidence": paths,
                    "evidence_available": False,
                    "fed_by": [],
                    "permission_basis": ["not-established"],
                    "live_validation_state": "none",
                }
            )
            continue
        states = [catalogue[s]["collector"]["live_validation_state"] for s in sources]
        weakest = min(states, key=lambda state: _PROVES[state])
        available = all(_produced(sources, path) for path in paths)
        answerable = "yes" if weakest == "full" and available else "unknown"
        out.append(
            {
                "id": rule["id"],
                "question": rule["title"],
                "answerable": answerable,
                "because": _because(weakest, available),
                "evidence": paths,
                "evidence_available": available,
                "fed_by": sources,
                "permission_basis": sorted(
                    {
                        permission
                        for s in sources
                        for permission in catalogue[s]["collector"]["permissions"]
                    }
                ),
                "live_validation_state": weakest,
            }
        )
    return {
        "$schema": registry.contract(CONTRACT),
        "engine_version": _version(),
        "questions": out,
    }


def _because(state: str, available: bool) -> str:
    """Why a question is not a yes, in the words of what is missing."""
    if not available:
        return (
            "the collector that feeds this rule does not produce the evidence "
            "it requires"
        )
    return {
        "full": (
            "the path that produces this evidence was observed against a real "
            "tenant, including the branch that reports a finding"
        ),
        "negative-only": (
            "it ran against a real tenant and the branch that reports a finding "
            "was never taken, so reporting one is unproved"
        ),
        "provider-only": (
            "the transport underneath has read a real tenant, this slice's own "
            "path has not"
        ),
        "none": "offline tests only",
    }[state]


def _produced(sources: list[str], path: str) -> bool:
    """Whether any feeding collector writes the fact at `path`.

    Read from the fixtures that define each shape a slice writes, because those
    are what the collector produces and they ship with the engine. Asking the
    live tenant would make this document a run result; asking a hand-written
    map would make it a fifth list.
    """
    from .engine import resolve

    for name in sources:
        for facts in _shape_facts(name):
            if resolve(facts, path).kind != "missing":
                return True
    return False


@cache
def _shape_facts(name: str) -> tuple[dict[str, Any], ...]:
    from .collecting import SLICES

    slice_ = SLICES[name]
    found = []
    for shape in (slice_.shaped_like, *slice_.also_shaped_like):
        for root in ("sharepoint", "entra", "."):
            candidate = packaged("fixtures") / root / f"{shape}.json"
            if candidate.exists():
                document = json.loads(candidate.read_text(encoding="utf-8"))
                found.append(document.get("facts", {}))
                break
    return tuple(found)


def _contracts() -> list[str]:
    return registry.SchemaRegistry.load(packaged("schemas")).contracts()


def _version() -> str:
    from . import __version__

    return __version__


def describe_questions(document: dict[str, Any]) -> str:
    """The answerability document for somebody reading rather than parsing.

    The totals lead, because they are the claim. A reader who stops after the
    first line should still leave with the honest number rather than the count
    of rule files.
    """
    entries = document["questions"]
    tally: dict[str, int] = {}
    for entry in entries:
        tally[entry["answerable"]] = tally.get(entry["answerable"], 0) + 1

    out = [
        f"m365-governance {document['engine_version']}",
        "",
        "Questions defensibly answerable from a real tenant",
        f"  yes {tally.get('yes', 0)}   unknown {tally.get('unknown', 0)}   "
        f"no {tally.get('no', 0)}   of {len(entries)}",
        "",
    ]
    for entry in entries:
        out += [
            f"  {entry['answerable'].upper():7} {entry['id']}",
            f"          {entry['question']}",
            f"          evidence   {', '.join(entry['evidence'])}",
            f"          collected  {', '.join(entry['fed_by']) or 'nothing'}",
            f"          permission {', '.join(entry['permission_basis'])}",
            f"          live       {entry['live_validation_state']}",
            f"          because    {entry['because']}",
        ]
    return "\n".join(out) + "\n"


def describe(document: dict[str, Any]) -> str:
    """The same manifest for somebody reading rather than parsing."""
    out = [
        f"m365-governance {document['engine_version']}, "
        f"contract {document['contract_version']}",
        "",
        "Capabilities",
    ]
    for capability in document["capabilities"]:
        collector = capability["collector"]
        rules = capability["consumed_by"]
        out += [
            f"  {capability['name']}",
            f"    {capability['describes']}",
            f"    reads      {', '.join(collector['reads']) or 'not-established'}",
            f"    needs      {', '.join(collector['permissions'])}",
            f"    live       {collector['live_validation']}",
            f"    rules      {', '.join(rules) if rules else capability['consumer']}",
        ]
    out += ["", f"Contracts  {len(document['contracts'])}"]
    out += [f"  {contract}" for contract in document["contracts"]]
    out += ["", f"Rules      {len(document['rules'])}"]
    return "\n".join(out) + "\n"
