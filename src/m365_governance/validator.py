"""Layers 2, 3 and 4.

Each constraint has exactly one owner. Where a constraint could live in more
than one layer, it belongs to the lowest layer that can express it completely.
See docs/JSON-SCHEMA-PLAN.md for the decision table.

Layer 2 never follows a reference. Everything in this module that does follow
one is layer 3 or above.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .loader import DocumentError, LoadedRule, load_json, load_rules
from .resources import packaged

# The same defect as the collector path, in the layer that would have made
# every other command fail silently: anchored to `__file__`, correct from
# `src/`, and pointing at `<prefix>/schemas` from site-packages.
SCHEMA_DIR = packaged("schemas")

INTERPOLATION = re.compile(r"\{([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*)\}")

#: Messages whose interpolations count as a dependency of the rule.
DECIDED_OUTCOMES = ("pass", "fail")

#: Messages printed precisely when evidence is absent, out of scope or
#: malformed. Layer 2 forbids interpolation in these; listed here so layer 3
#: never counts them as dependencies.
FAILURE_OUTCOMES = ("unknown", "not_applicable", "invalid_evidence")


@dataclass(frozen=True)
class Problem:
    layer: int
    code: str
    location: str
    message: str

    def __str__(self) -> str:
        return f"[L{self.layer} {self.code}] {self.location}: {self.message}"


def _schema(name: str) -> dict:
    return load_json(SCHEMA_DIR / name)


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(name), format_checker=FormatChecker())


# ---------------------------------------------------------------------------
# Layer 2: one document, no outside knowledge
# ---------------------------------------------------------------------------


def validate_structure(data: dict, schema_name: str, location: str) -> list[Problem]:
    problems: list[Problem] = []
    for error in sorted(_validator(schema_name).iter_errors(data), key=str):
        pointer = "/".join(str(p) for p in error.absolute_path) or "<root>"
        problems.append(Problem(2, "schema", f"{location}#{pointer}", error.message))
    return problems


# ---------------------------------------------------------------------------
# Layer 3: one document, references followed
# ---------------------------------------------------------------------------


def evidence_paths(rule: dict) -> set[str]:
    return {req["path"] for req in rule.get("evidence_requirements", [])}


def required_paths(rule: dict) -> set[str]:
    return {
        req["path"]
        for req in rule.get("evidence_requirements", [])
        if req.get("required") is True
    }


def referenced_paths(rule: dict) -> set[str]:
    """Paths named by the condition and the applicability."""
    found = set()
    for key in ("condition", "applicability"):
        block = rule.get(key)
        if isinstance(block, dict) and "evidence" in block:
            found.add(block["evidence"])
    return found


def interpolated_paths(message: str) -> set[str]:
    return set(INTERPOLATION.findall(message))


def decision_dependencies(rule: dict) -> set[str]:
    """condition ∪ applicability ∪ interp(pass) ∪ interp(fail)."""
    deps = referenced_paths(rule)
    outcomes = rule.get("outcomes", {})
    for name in DECIDED_OUTCOMES:
        message = outcomes.get(name, {}).get("message", "")
        deps |= interpolated_paths(message)
    return deps


def validate_semantics(rule: dict, location: str) -> list[Problem]:
    problems: list[Problem] = []
    declared = evidence_paths(rule)
    required = required_paths(rule)
    dependencies = decision_dependencies(rule)

    undeclared = referenced_paths(rule) - declared
    for path in sorted(undeclared):
        problems.append(
            Problem(
                3,
                "undeclared-evidence",
                location,
                f"the condition or applicability reads {path!r}, which "
                f"evidence_requirements does not declare",
            )
        )

    outcomes = rule.get("outcomes", {})
    for name in DECIDED_OUTCOMES:
        message = outcomes.get(name, {}).get("message", "")
        for path in sorted(interpolated_paths(message) - declared):
            problems.append(
                Problem(
                    3,
                    "undeclared-interpolation",
                    location,
                    f"the {name} message interpolates {path!r}, which "
                    f"evidence_requirements does not declare",
                )
            )

    for path in sorted(required - dependencies):
        problems.append(
            Problem(
                3,
                "unused-required-evidence",
                location,
                f"{path!r} is declared required but never consumed by the "
                f"condition, the applicability, or a pass/fail message. It "
                f"manufactures unknown on resources the rule could decide",
            )
        )

    for path in sorted(dependencies - required):
        problems.append(
            Problem(
                3,
                "undeclared-dependency",
                location,
                f"the rule decides using {path!r} without declaring it required",
            )
        )

    return problems


# ---------------------------------------------------------------------------
# Layer 4: every document together
# ---------------------------------------------------------------------------


def validate_repository(rules: list[LoadedRule]) -> list[Problem]:
    problems: list[Problem] = []
    seen: dict[str, Path] = {}
    for loaded in rules:
        rule_id = loaded.data.get("id")
        if not rule_id:
            continue
        if rule_id in seen:
            problems.append(
                Problem(
                    4,
                    "duplicate-id",
                    str(loaded.path),
                    f"id {rule_id!r} is already used by {seen[rule_id]}. "
                    f"Ids are never reused",
                )
            )
        else:
            seen[rule_id] = loaded.path
    return problems


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def validate_rules(directory: Path) -> list[Problem]:
    """Every layer, in order. Layer N assumes layer N-1 passed."""
    try:
        rules = load_rules(directory)
    except DocumentError as exc:
        return [Problem(1, "parse", str(directory), str(exc))]

    problems: list[Problem] = []
    for loaded in rules:
        location = str(loaded.path)
        structural = validate_structure(loaded.data, "rule.schema.json", location)
        problems.extend(structural)
        if structural:
            # Layer 3 reads fields layer 2 has not vouched for. Skipping it
            # here is not leniency: it prevents a cascade of derived errors
            # that hide the one that matters.
            continue
        problems.extend(validate_semantics(loaded.data, location))

    problems.extend(validate_repository(rules))
    return problems


def validate_evidence_document(data: dict, location: str) -> list[Problem]:
    """Validated against the contract the **document** declares.

    Not against whichever evidence schema this engine happens to ship. A newer
    version reading an older document would be reinterpreting it rather than
    checking it, and the reinterpretation would arrive looking like a finding
    about somebody's tenant.
    """
    from . import registry as registry_module

    contracts = _registry()
    try:
        problems = contracts.problems(data)
    except registry_module.Undeclared as exc:
        return [Problem(2, "schema", location, str(exc))]
    except registry_module.UnknownContract as exc:
        return [Problem(2, "schema", location, str(exc))]

    return [
        Problem(
            2,
            "schema",
            f"{location}#{problem.split(':', 1)[0]}",
            problem.split(": ", 1)[-1],
        )
        for problem in problems
    ]


@lru_cache(maxsize=1)
def _registry():
    from . import registry as registry_module

    return registry_module.SchemaRegistry.load(SCHEMA_DIR)
