"""What the engine produces. Never written back into the evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not-applicable"
    INVALID_EVIDENCE = "invalid-evidence"
    #: Not authorable by a rule. It describes the engine, not the resource.
    ERROR = "error"

    @property
    def is_answer(self) -> bool:
        """True when the rule established something about the resource."""
        return self in (Outcome.PASS, Outcome.FAIL)


#: An outcome a rule may author a message for.
AUTHORABLE = (
    Outcome.PASS,
    Outcome.FAIL,
    Outcome.UNKNOWN,
    Outcome.NOT_APPLICABLE,
    Outcome.INVALID_EVIDENCE,
)

_MESSAGE_KEY = {
    Outcome.PASS: "pass",
    Outcome.FAIL: "fail",
    Outcome.UNKNOWN: "unknown",
    Outcome.NOT_APPLICABLE: "not_applicable",
    Outcome.INVALID_EVIDENCE: "invalid_evidence",
}


def message_key(outcome: Outcome) -> str | None:
    return _MESSAGE_KEY.get(outcome)


@dataclass(frozen=True)
class EvidenceUsed:
    """A path the engine read, and what it found. Carried so a reader can see
    the derivation next to the conclusion."""

    path: str
    state: str
    exact: Any = None
    lower_bound: int | None = None
    upper_bound: int | None = None
    detail: str | None = None

    def describe(self) -> str:
        if isinstance(self.exact, bool):
            return "true" if self.exact else "false"
        if self.exact is not None:
            return str(self.exact)
        if self.lower_bound is not None:
            return f"at least {self.lower_bound}"
        return f"<{self.state}>"


@dataclass
class Result:
    rule_id: str
    rule_version: str
    schema_version: str
    resource_id: str
    resource_type: str
    outcome: Outcome
    message: str
    basis_type: str
    severity: str
    evidence_used: list[EvidenceUsed] = field(default_factory=list)
    limitation: str = ""
    sources: list[dict] = field(default_factory=list)
    remediation: str = ""
    message_degraded: bool = False
    engine_detail: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "schema_version": self.schema_version,
            "resource": {"id": self.resource_id, "type": self.resource_type},
            "outcome": self.outcome.value,
            "message": self.message,
            "basis": self.basis_type,
            "severity": self.severity,
            "evidence_used": [
                {
                    "path": e.path,
                    "state": e.state,
                    "value": e.exact,
                    "lower_bound": e.lower_bound,
                    "upper_bound": e.upper_bound,
                    "detail": e.detail,
                }
                for e in self.evidence_used
            ],
            "passes_without_resolving": self.limitation,
            "sources": self.sources,
            "remediation": self.remediation,
            "message_degraded": self.message_degraded,
            "engine_detail": self.engine_detail,
        }


@dataclass
class Run:
    """One evaluation of a rule set against one evidence document."""

    results: list[Result]
    provenance: dict
    coverage: dict
    resource: dict

    def counts(self) -> dict[str, int]:
        tally = {o.value: 0 for o in Outcome}
        for result in self.results:
            tally[result.outcome.value] += 1
        return tally

    def to_dict(self) -> dict:
        return {
            "provenance": self.provenance,
            "coverage": self.coverage,
            "resource": self.resource,
            "counts": self.counts(),
            "results": [r.to_dict() for r in self.results],
        }
