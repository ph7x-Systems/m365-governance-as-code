"""What the engine produces. Never written back into the evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from . import attention as attention_module
from . import identity, registry


class Outcome(StrEnum):
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
    #: The resource this result is about, as a structured reference.
    resource_ref: dict
    outcome: Outcome
    message: str
    basis_type: str
    severity: str
    #: The rule's own name. An id identifies; a title says what was checked,
    #: and it is what a person cites in a sentence. A report that carries only
    #: the message loses the name of the thing that produced it.
    title: str = ""
    evidence_used: list[EvidenceUsed] = field(default_factory=list)
    limitation: str = ""
    sources: list[dict] = field(default_factory=list)
    remediation: str = ""
    message_degraded: bool = False
    engine_detail: str = ""

    def to_dict(self) -> dict:
        document = {
            "rule_id": self.rule_id,
            "title": self.title,
            "rule_version": self.rule_version,
            "schema_version": self.schema_version,
            "resource": dict(self.resource_ref),
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
        # Derived from the block above rather than from the dataclass, so the
        # judgement is made from exactly the facts a consumer receives. Anything
        # it could read that a reader cannot would be a judgement nobody can
        # check.
        document["attention"] = attention_module.for_result(document)
        return document

    @classmethod
    def from_dict(cls, data: dict) -> Result:
        """Rebuild a result from its JSON form.

        The round trip has to be lossless, because `report` re-renders a stored
        run without re-evaluating it. A field dropped here would be a field
        that silently disappears from a report the second time somebody looks
        at it, which is worse than not storing it at all.
        """
        resource = data.get("resource", {})
        return cls(
            rule_id=data["rule_id"],
            title=data.get("title", ""),
            rule_version=data.get("rule_version", ""),
            schema_version=data.get("schema_version", ""),
            resource_ref=identity.ref(resource),
            outcome=Outcome(data["outcome"]),
            message=data.get("message", ""),
            basis_type=data.get("basis", "<unknown>"),
            severity=data.get("severity", "<unknown>"),
            evidence_used=[
                EvidenceUsed(
                    path=e["path"],
                    state=e.get("state", ""),
                    exact=e.get("value"),
                    lower_bound=e.get("lower_bound"),
                    upper_bound=e.get("upper_bound"),
                    detail=e.get("detail"),
                )
                for e in data.get("evidence_used", [])
            ],
            limitation=data.get("passes_without_resolving", ""),
            sources=data.get("sources", []),
            remediation=data.get("remediation", ""),
            message_degraded=data.get("message_degraded", False),
            engine_detail=data.get("engine_detail", ""),
        )


@dataclass
class Run:
    """One evaluation of a rule set against one evidence document."""

    results: list[Result]
    provenance: dict
    coverage: dict
    resource: dict
    #: What kind of resource this is, when the evidence says. Used to group a
    #: report, never to drop anything from one.
    resource_class: str = ""
    #: Why it was classified that way, so a reader argues with the precedence
    #: rather than with the label.
    class_reason: str = ""
    #: Set when a profile put this resource below the fold. The findings are
    #: still here, still counted, still printed.
    set_aside: bool = False
    #: Where the rules came from: shipped with this version, or a path the
    #: caller supplied. A finding produced by rules nobody can identify is not
    #: reproducible, so this travels with the result rather than being known
    #: only by whoever typed the command.
    rule_source: str = ""

    def counts(self) -> dict[str, int]:
        tally = {o.value: 0 for o in Outcome}
        for result in self.results:
            tally[result.outcome.value] += 1
        return tally

    @classmethod
    def from_dict(cls, data: dict) -> Run:
        return cls(
            results=[Result.from_dict(r) for r in data.get("results", [])],
            provenance=data.get("provenance", {}),
            coverage=data.get("coverage", {}),
            resource=data.get("resource", {}),
            resource_class=data.get("resource_class", ""),
            class_reason=data.get("class_reason", ""),
            set_aside=data.get("set_aside", False),
            rule_source=data.get("rule_source", ""),
        )

    def to_dict(self) -> dict:
        results = [r.to_dict() for r in self.results]
        return {
            "$schema": registry.contract("run"),
            "provenance": self.provenance,
            "coverage": self.coverage,
            "resource": self.resource,
            "resource_class": self.resource_class,
            "class_reason": self.class_reason,
            "set_aside": self.set_aside,
            "rule_source": self.rule_source,
            "counts": self.counts(),
            "results": results,
            "attention": attention_module.for_run(results, self.coverage),
        }


class DuplicateResource(ValueError):
    """Two evidence documents describe the same resource id.

    A `ValueError`, so the existing contract holds, and named, so the command
    line can turn it into one clear sentence instead of a traceback. It is the
    engine refusing to average two answers about one resource, which is the
    same refusal as scoring: a run set that counted a site twice would report a
    number no tenant has.
    """


@dataclass
class RunSet:
    """A stored evaluation over more than one resource.

    A directory is a stable input shape even when it contains one document
    today and fifty tomorrow, so its result is a first-class envelope rather
    than a list that only the command which produced it understands.

    `expected` is deliberately optional. Counting the documents that exist
    proves how many resources were observed; it cannot prove how many the
    identity failed to return. Absence of that fact is stored as
    `not-established`, never as complete coverage.
    """

    runs: list[Run]
    coverage: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        keys = [identity.key(run.resource) for run in self.runs]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        if duplicates:
            # Assembled for the message only. Comparison above is structural;
            # nothing reads this string back.
            joined = ", ".join(
                identity.readable(dict(zip(identity.FIELDS, k, strict=False)))
                for k in duplicates
            )
            raise DuplicateResource(
                f"a run set describes the same resource twice: {joined}"
            )

    def counts(self) -> dict[str, int]:
        tally = {o.value: 0 for o in Outcome}
        for run in self.runs:
            for name, value in run.counts().items():
                tally[name] += value
        return tally

    def by_class(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for run in self.runs:
            name = run.resource_class or "unclassified"
            tally[name] = tally.get(name, 0) + 1
        return tally

    def run_coverage(self) -> dict:
        if self.coverage:
            return self.coverage
        return {
            "state": "not-established",
            "observed": len(self.runs),
            "expected": None,
            "detail": (
                f"{len(self.runs)} "
                f"{'resource is' if len(self.runs) == 1 else 'resources are'} "
                "stored. The total number the identity was expected to reach "
                "was not recorded, so this run does not establish complete "
                "coverage."
            ),
        }

    def to_dict(self) -> dict:
        return {
            # The exact contract this document claims. It replaces
            # `run_schema_version: "1.0"`, a second version maintained by hand
            # in a form that could not express the one in the schema's own $id.
            "$schema": registry.contract("run-set"),
            "resources": len(self.runs),
            "by_class": self.by_class(),
            "set_aside": sum(1 for run in self.runs if run.set_aside),
            "counts": self.counts(),
            "run_coverage": self.run_coverage(),
            "runs": [run.to_dict() for run in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> RunSet:
        return cls(
            runs=[Run.from_dict(run) for run in data.get("runs", [])],
            coverage=data.get("run_coverage", {}),
        )
