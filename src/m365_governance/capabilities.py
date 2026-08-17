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
    by_resource: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rule in loaded:
        key = (rule.get("service", ""), rule.get("resource_type", ""))
        by_resource.setdefault(key, []).append(rule)

    return {
        "$schema": registry.contract(CONTRACT),
        "engine_version": _version(),
        "contract_version": collecting._contract_version(),
        "capabilities": [
            _capability(chosen, by_resource)
            for chosen in sorted(collecting.SLICES.values(), key=lambda s: s.name)
        ],
        "contracts": sorted(_contracts()),
        "rules": sorted(
            (_rule(rule) for rule in loaded), key=lambda r: str(r["id"])
        ),
    }


def _capability(
    chosen: collecting.Slice, by_resource: dict[tuple[str, str], list[dict[str, Any]]]
) -> dict[str, Any]:
    """One slice, and everything that is true of it.

    The rules are not declared on the slice and are not counted here either:
    they are the rules whose workload and resource type match what this slice
    produces. A declared list would be a second place to update, and the first
    time somebody added a rule and forgot, the manifest would understate the
    product while looking maintained.
    """
    workload, resource_type = _produces(chosen)
    consuming = by_resource.get((workload, resource_type), [])

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
            "live_validation": chosen.live,
        },
        "produces": {"workload": workload, "resource_type": resource_type},
        "consumed_by": (
            [str(rule["id"]) for rule in sorted(consuming, key=lambda r: str(r["id"]))]
            if chosen.produces_findings
            else []
        ),
        # Named whenever no rule reads it, which is the price of the exception
        # to the twin rule. Without it, "no rule" reads as "nobody looked".
        "consumer": chosen.consumed_by,
    }


def _produces(chosen: collecting.Slice) -> tuple[str, str]:
    """The workload and resource type this slice writes evidence about.

    Read from the fixture the slice is already paired with, which is the one
    place that has to be right for the profile test to pass. A second
    declaration would be a second thing to keep true.
    """
    from .loader import load_json

    for folder in ("sharepoint", "entra"):
        path = packaged("fixtures") / folder / f"{chosen.shaped_like}.json"
        if path.is_file():
            resource = load_json(path).get("resource", {})
            return str(resource.get("workload", "")), str(resource.get("type", ""))
    return "", ""


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


def _contracts() -> list[str]:
    return registry.SchemaRegistry.load(packaged("schemas")).contracts()


def _version() -> str:
    from . import __version__

    return __version__


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
