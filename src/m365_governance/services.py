"""What was observed, by service and by area, from the documents themselves.

**THE PRODUCT IS NOT A COLLECTION OF CHECKS AND SHOULD NOT INTRODUCE ITSELF AS
ONE.** A reader opening a result sees a list of rule identifiers grouped by
whatever the interface decided to group them by, which describes the engine's
internals rather than their tenant. What they need first is which parts of
Microsoft 365 were looked at, how far each reading got, and which of them
reached a conclusion at all.

Everything here is DERIVED from what the collectors and the rules already
publish. There is no `if licensing` and no per-service special case: a service
is the workload on a resource, an area is what the collector declared it
requested, and a conclusion is a result whose evidence resolves into that area.
A projection that needed a branch per service would be a second place to add a
service, and there are four fewer of those in this tree than there were.

**NO COVERAGE PERCENTAGE, AND NONE IS DERIVABLE FROM THIS.** `21 conclusions`
is twenty-one conclusions. It is not twenty-one out of some total, because the
denominator would be the number of questions somebody could have asked, which
nobody knows. `D5` forbids the aggregate and this is the shape that would
smuggle one in.
"""

from __future__ import annotations

from typing import Any

from . import attribution

#: How far a reading of one area got, weakest first. Ordered so a service can
#: report its weakest area without anybody comparing strings.
STATES = (
    "not-observed",
    "refused",
    "partial",
    "observed",
)

#: What a collector's coverage block calls each of those. Read from the
#: evidence rather than assumed: `not-supported` is the product saying it does
#: not implement the reading, which is a refusal of a different kind from a
#: tenant declining to answer, and both are distinct from partial.
_FROM_COVERAGE = {
    "missing": "not-observed",
    "not-supported": "refused",
    "permission-denied": "refused",
    "invalid": "refused",
    "partial": "partial",
}


def observed(runs: list[Any], documents: list[dict]) -> dict[str, Any]:
    """Services and areas, as this workspace actually read them.

    `runs` carry the conclusions and `documents` carry what was collected. Both
    are needed and neither is enough: a run says what was decided, a document
    says what was looked at, and an area that was collected and decided nothing
    is the case a list of findings cannot show.
    """
    services: dict[str, dict[str, Any]] = {}

    for document in documents:
        workload = str((document.get("resource") or {}).get("workload") or "unknown")
        service = services.setdefault(workload, {"service": workload, "areas": {}})
        coverage = document.get("coverage") or {}
        unavailable = coverage.get("unavailable") or {}

        for name in coverage.get("requested") or ():
            area = service["areas"].setdefault(
                str(name),
                {
                    "area": str(name),
                    "state": "not-observed",
                    "conclusions": 0,
                    "unresolved": 0,
                    "acquisition": set(),
                    "population": 0,
                },
            )
            entry = unavailable.get(name)
            state = (
                _FROM_COVERAGE.get(str((entry or {}).get("state")), "refused")
                if entry
                else "observed"
            )
            if STATES.index(state) > STATES.index(area["state"]):
                area["state"] = state

            provenance = document.get("provenance") or {}
            if provenance.get("collector"):
                area["acquisition"].add(str(provenance["collector"]))
            if state != "not-observed":
                area["population"] += 1

    # THE CONCLUSIONS, ATTRIBUTED TO THE AREA THEY WERE DECIDED FROM. A result
    # names the evidence paths it used and the first segment of a path is the
    # fact block, which is the area. Nothing is counted twice: a rule reading
    # two areas is a conclusion in both, and saying otherwise would be picking
    # one for tidiness.
    for run in runs:
        workload = str((getattr(run, "resource", None) or {}).get("workload") or "")
        service = services.get(workload)
        if service is None:
            continue
        for result in getattr(run, "results", ()):
            outcome = str(getattr(result.outcome, "value", result.outcome))
            used = [
                attribution.block_of(str(getattr(e, "path", "")))
                for e in getattr(result, "evidence_used", ()) or ()
            ]
            for block in {b for b in used if b}:
                area = service["areas"].get(block)
                if area is None:
                    continue
                if outcome in ("unknown", "invalid_evidence"):
                    area["unresolved"] += 1
                elif outcome != "not_applicable":
                    area["conclusions"] += 1

    return {
        "services": [
            {
                "service": name,
                # The weakest area a service has, so a service that read four
                # things and was refused one does not report as observed.
                "state": min(
                    (a["state"] for a in service["areas"].values()),
                    key=STATES.index,
                    default="not-observed",
                ),
                "conclusions": sum(a["conclusions"] for a in service["areas"].values()),
                "unresolved": sum(a["unresolved"] for a in service["areas"].values()),
                "areas": [
                    {**area, "acquisition": sorted(area["acquisition"])}
                    for _, area in sorted(service["areas"].items())
                ],
            }
            for name, service in sorted(services.items())
        ]
    }


def sentence(service: dict[str, Any]) -> str:
    """One service, as a person reads it.

    THE HARD PART IS THE SERVICE THAT COLLECTED AND CONCLUDED NOTHING. A count
    of zero beside a service that was read properly looks like a failure, and
    it is the opposite: Licensing feeds no rule by a recorded decision, so
    `evidence collected, no governance conclusion` is the accurate sentence and
    `0 conclusions` is a misleading one.
    """
    areas = len(service["areas"])
    read = sum(1 for a in service["areas"] if a["state"] != "not-observed")

    if service["conclusions"]:
        return (
            f"{service['conclusions']} conclusion"
            f"{'' if service['conclusions'] == 1 else 's'} "
            f"from {read} of {areas} area{'' if areas == 1 else 's'} read"
        )
    if read:
        return (
            f"Evidence collected from {read} area{'' if read == 1 else 's'}. "
            "No governance conclusion."
        )
    return "Not observed."
