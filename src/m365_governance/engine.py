"""The engine.

It applies the resolution order, reasons from bounds where they exist, and
returns `unknown` only when the missing information could change the outcome.

It never alters evidence. It never classifies: `basis` is authored, and the
engine's only relationship with it is to carry it into the result unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .results import EvidenceUsed, Outcome, Result, Run, message_key

INTERPOLATION = re.compile(r"\{([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*)\}")

#: Rendered in place of a value the collector did not return, when the outcome
#: was decided without it. Printing nothing would read as a value of zero.
NOT_COLLECTED = "<not collected>"

# A condition describes the state the rule is looking for, and finding it is a
# failure. Both authored rules are written this way: `owners.count less-than 2`
# and `items.count greater-than 100000` are both the case being reported.
CONDITION_TRUE_MEANS = Outcome.FAIL


@dataclass(frozen=True)
class Resolved:
    """What the engine found at one evidence path."""

    path: str
    kind: str  # exact | bounded | absent | invalid
    value: Any = None
    lower: int | None = None
    upper: int | None = None
    state: str = ""
    detail: str | None = None

    def as_used(self) -> EvidenceUsed:
        return EvidenceUsed(
            path=self.path,
            state=self.state,
            exact=self.value,
            lower_bound=self.lower,
            upper_bound=self.upper,
            detail=self.detail,
        )


def _absent(path: str, state: str, detail: str | None = None) -> Resolved:
    return Resolved(path=path, kind="absent", state=state, detail=detail)


def resolve(facts: dict, path: str) -> Resolved:
    """Read one path out of `facts`.

    Every path is read, with one exception: `<aggregate>.count` is derived from
    the expansion fields documented in EVIDENCE-SCHEMA section 8. A rule author
    must not have to reason about partial expansion, so the engine turns it
    into a bound.
    """
    segments = path.split(".")
    node: Any = facts
    for index, segment in enumerate(segments):
        if not isinstance(node, dict):
            return _absent(
                path, "missing", f"{'.'.join(segments[:index])} is not a mapping"
            )
        is_last = index == len(segments) - 1
        if "expansion_complete" in node and is_last and segment == "count":
            return _derive_count(path, node)
        if segment not in node:
            # The block that would have contained this path reported its own
            # state. A parent that came back invalid or permission-denied is
            # not the same as a path nobody collected, and collapsing the two
            # would turn a broken collector into a clean `unknown`.
            parent_state = node.get("state")
            if parent_state == "invalid":
                return Resolved(
                    path=path,
                    kind="invalid",
                    state=parent_state,
                    detail=node.get("detail"),
                )
            if parent_state and parent_state != "observed":
                return _absent(path, parent_state, node.get("detail"))
            return _absent(path, "missing", "not present in the evidence")
        node = node[segment]

    if not isinstance(node, dict) or "state" not in node:
        return _absent(path, "missing", "not a fact node")

    state = node["state"]
    if state == "invalid":
        return Resolved(
            path=path, kind="invalid", state=state, detail=node.get("detail")
        )
    if state == "observed":
        return Resolved(path=path, kind="exact", value=node.get("value"), state=state)
    if state == "partial" and isinstance(node.get("value"), (int, float)):
        # A partial count is a lower bound, and the model already says why:
        # evidence is monotonic, so collecting more can add and never remove.
        # A collector that stopped at 20,000 items saw at least what it counted.
        # Treating it as absent would throw away an answer the evidence gives.
        return Resolved(
            path=path,
            kind="bounded",
            lower=node["value"],
            upper=None,
            state=state,
            detail=node.get("detail") or "counted in part: the value is a lower bound",
        )
    return _absent(path, state, node.get("detail"))


def _derive_count(path: str, node: dict) -> Resolved:
    state = node.get("state", "missing")
    if state == "invalid":
        # An aggregate that came back malformed must not be laundered into
        # `unknown`. The fix for one is to collect again; the fix for the
        # other is to repair the collector.
        return Resolved(
            path=path, kind="invalid", state=state, detail=node.get("detail")
        )
    if state not in ("observed", "partial"):
        return _absent(path, state, node.get("detail"))
    if node.get("expansion_complete") is True:
        return Resolved(
            path=path, kind="exact", value=node.get("effective_count"), state="observed"
        )
    return Resolved(
        path=path,
        kind="bounded",
        lower=node.get("minimum_count"),
        upper=None,
        state="partial",
        detail="expansion incomplete: the count is a lower bound",
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

_EXACT = {
    "equals": lambda a, b: a == b,
    "not-equals": lambda a, b: a != b,
    "less-than": lambda a, b: a < b,
    "less-than-or-equal": lambda a, b: a <= b,
    "greater-than": lambda a, b: a > b,
    "greater-than-or-equal": lambda a, b: a >= b,
    "contains": lambda a, b: b in a,
    "not-contains": lambda a, b: b not in a,
    "in": lambda a, b: a in b,
    "not-in": lambda a, b: a not in b,
}


def compare(resolved: Resolved, operator: str, value: Any) -> bool | None:
    """True, False, or None when the evidence does not settle it."""
    if resolved.kind == "exact":
        return _compare_exact(resolved.value, operator, value)
    if resolved.kind == "bounded":
        return _compare_bounded(resolved, operator, value)
    return None


def _compare_exact(observed: Any, operator: str, value: Any) -> bool | None:
    if operator == "exists":
        return observed is not None
    if operator == "not-exists":
        return observed is None
    try:
        return _EXACT[operator](observed, value)
    except (TypeError, KeyError):
        return None


def _compare_bounded(resolved: Resolved, operator: str, value: Any) -> bool | None:
    """Monotonic reasoning: collecting more can add, never remove.

    Each operator has a side on which a partial answer is already final. See
    the table in docs/ARCHITECTURE.md.
    """
    lower, upper = resolved.lower, resolved.upper

    if operator == "exists":
        return True if (lower or 0) >= 1 else None
    if operator == "not-exists":
        return False if (lower or 0) >= 1 else None

    if not isinstance(value, (int, float)) or lower is None:
        return None

    if operator == "greater-than":
        if lower > value:
            return True
        return False if upper is not None and upper <= value else None
    if operator == "greater-than-or-equal":
        if lower >= value:
            return True
        return False if upper is not None and upper < value else None
    if operator == "less-than":
        if upper is not None and upper < value:
            return True
        return False if lower >= value else None
    if operator == "less-than-or-equal":
        if upper is not None and upper <= value:
            return True
        return False if lower > value else None

    # equals and not-equals are never decidable from a bound alone.
    return None


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_rule(rule: dict, evidence: dict) -> Result:
    try:
        return _evaluate(rule, evidence)
    except Exception as exc:  # noqa: BLE001 - the engine reports its own faults
        resource = evidence.get("resource", {})
        return Result(
            rule_id=rule.get("id", "<unknown>"),
            title=str(rule.get("title", "")),
            rule_version=str(rule.get("version", "")),
            schema_version=str(rule.get("schema_version", "")),
            resource_id=resource.get("id", "<unknown>"),
            resource_type=resource.get("type", "<unknown>"),
            outcome=Outcome.ERROR,
            message=(
                "The evaluation did not finish. This describes the engine, "
                "not the resource, and no conclusion may be drawn from it."
            ),
            basis_type=rule.get("basis", {}).get("type", "<unknown>"),
            severity=rule.get("severity", {}).get("default", "<unknown>"),
            engine_detail=f"{type(exc).__name__}: {exc}",
        )


def _evaluate(rule: dict, evidence: dict) -> Result:
    facts = evidence.get("facts", {})
    resource = evidence.get("resource", {})

    resolutions = {
        req["path"]: resolve(facts, req["path"])
        for req in rule.get("evidence_requirements", [])
    }

    def build(outcome: Outcome) -> Result:
        key = message_key(outcome)
        # Indexed, not `.get`. Layer 2 guarantees all five messages exist, so
        # a missing one is an engine-level fault and must surface as `error`.
        # Rendering an empty string would publish a finding with no text.
        template = rule["outcomes"][key]["message"]
        message, degraded = _render(template, resolutions)
        return Result(
            rule_id=rule["id"],
            title=str(rule.get("title", "")),
            rule_version=str(rule["version"]),
            schema_version=str(rule["schema_version"]),
            resource_id=resource.get("id", "<unknown>"),
            resource_type=resource.get("type", "<unknown>"),
            outcome=outcome,
            message=message,
            basis_type=rule["basis"]["type"],
            severity=rule["severity"]["default"],
            evidence_used=[resolutions[p].as_used() for p in sorted(resolutions)],
            limitation=rule["limitations"]["passes_without_resolving"].strip(),
            sources=rule["basis"].get("sources", []),
            remediation=rule.get("remediation", "").strip(),
            message_degraded=degraded,
        )

    # 1. invalid-evidence, first, so a malformed value cannot vanish beneath
    #    an applicability decision.
    if any(r.kind == "invalid" for r in resolutions.values()):
        return build(Outcome.INVALID_EVIDENCE)

    # 2. not-applicable.
    applicability = rule.get("applicability")
    if applicability:
        verdict = compare(
            resolutions.get(
                applicability["evidence"],
                resolve(facts, applicability["evidence"]),
            ),
            applicability["operator"],
            applicability.get("value"),
        )
        if verdict is None:
            # Whether the rule speaks about this resource is itself unknown.
            return build(Outcome.UNKNOWN)
        if verdict is False:
            return build(Outcome.NOT_APPLICABLE)

    # 3. unknown, only when the outcome depends on what was not collected.
    condition = rule["condition"]
    verdict = compare(
        resolutions.get(condition["evidence"], resolve(facts, condition["evidence"])),
        condition["operator"],
        condition.get("value"),
    )
    if verdict is None:
        return build(Outcome.UNKNOWN)

    # 4. pass or fail.
    if verdict is True:
        return build(CONDITION_TRUE_MEANS)
    return build(Outcome.PASS)


def _render(template: str, resolutions: dict[str, Resolved]) -> tuple[str, bool]:
    degraded = False
    rendered = template.strip()
    for path in INTERPOLATION.findall(template):
        resolved = resolutions.get(path)
        if resolved is None or resolved.kind in ("absent", "invalid"):
            replacement = NOT_COLLECTED
            degraded = True
        elif resolved.kind == "bounded":
            replacement = f"at least {resolved.lower}"
        else:
            replacement = str(resolved.value)
        rendered = rendered.replace("{" + path + "}", replacement)
    return " ".join(rendered.split()), degraded


def evaluate(rules: list[dict], evidence: dict) -> Run:
    """Every applicable rule, plus the label the report groups by.

    The class never changes an outcome. It is carried so a reader can move
    plumbing down the page without anybody deciding, upstream, that plumbing
    is not worth evaluating.
    """
    from .classifying import classify

    classification = classify(evidence)
    applicable = [
        r
        for r in rules
        if r.get("resource_type") == evidence.get("resource", {}).get("type")
    ]
    return Run(
        results=[evaluate_rule(rule, evidence) for rule in applicable],
        provenance=evidence.get("provenance", {}),
        coverage=evidence.get("coverage", {}),
        resource=evidence.get("resource", {}),
        resource_class=classification.kind.value,
        class_reason=classification.because,
    )
