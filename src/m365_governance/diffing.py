"""Comparing two runs.

The question a periodic audit actually asks is not "what is wrong today" but
"what changed, and was it the estate or was it us".

Both halves matter, so a diff reports the rule version alongside the outcome.
A result that moved because somebody edited the rule is not a result that
moved because somebody removed an owner, and a comparison that cannot tell
them apart is worse than no comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .results import EvidenceUsed, Outcome, Result, Run, RunSet

#: Movements worth leading with. A pass turning into anything else is the top
#: of a report; anything turning into a pass is the bottom.
_WEIGHT = {
    Outcome.FAIL: 0,
    Outcome.INVALID_EVIDENCE: 1,
    Outcome.ERROR: 2,
    Outcome.UNKNOWN: 3,
    Outcome.NOT_APPLICABLE: 4,
    Outcome.PASS: 5,
}


@dataclass
class EvidenceChange:
    path: str
    before: str
    after: str


@dataclass
class RuleChange:
    rule_id: str
    before: Result | None
    after: Result | None
    evidence: list[EvidenceChange] = field(default_factory=list)
    rule_version_changed: bool = False

    @property
    def kind(self) -> str:
        if self.before is None:
            return "added"
        if self.after is None:
            return "removed"
        return "changed"


def _describe(used: EvidenceUsed) -> str:
    return used.describe()


def _evidence_changes(before: Result, after: Result) -> list[EvidenceChange]:
    old = {e.path: e for e in before.evidence_used}
    new = {e.path: e for e in after.evidence_used}
    changes = []
    for path in sorted(set(old) | set(new)):
        a = _describe(old[path]) if path in old else "<not required>"
        b = _describe(new[path]) if path in new else "<not required>"
        if a != b:
            changes.append(EvidenceChange(path=path, before=a, after=b))
    return changes


def compare(before: Run, after: Run) -> list[RuleChange]:
    old = {r.rule_id: r for r in before.results}
    new = {r.rule_id: r for r in after.results}
    changes: list[RuleChange] = []

    for rule_id in sorted(set(old) | set(new)):
        a, b = old.get(rule_id), new.get(rule_id)
        if a is None or b is None:
            changes.append(RuleChange(rule_id=rule_id, before=a, after=b))
            continue
        version_moved = a.rule_version != b.rule_version
        evidence = _evidence_changes(a, b)
        if a.outcome is b.outcome and not evidence and not version_moved:
            continue
        changes.append(
            RuleChange(
                rule_id=rule_id,
                before=a,
                after=b,
                evidence=evidence,
                rule_version_changed=version_moved,
            )
        )

    def key(change: RuleChange) -> tuple:
        outcome = change.after.outcome if change.after else Outcome.PASS
        return (_WEIGHT.get(outcome, 9), change.rule_id)

    return sorted(changes, key=key)


def to_markdown(before: Run, after: Run) -> str:
    changes = compare(before, after)
    lines: list[str] = ["# What changed", ""]

    resource = after.resource.get("id") or before.resource.get("id", "<unknown>")
    lines.append(f"- Resource: `{resource}`")
    lines.append(f"- Before: {before.provenance.get('collected_at', '?')}")
    lines.append(f"- After:  {after.provenance.get('collected_at', '?')}")
    lines.append("")

    if not changes:
        lines.append(
            "Nothing changed. Same outcomes, same evidence, same rule versions."
        )
        return "\n".join(lines) + "\n"

    moved = [
        c
        for c in changes
        if c.kind == "changed" and c.before.outcome is not c.after.outcome
    ]
    lines.append(
        f"{len(changes)} {'rule differs' if len(changes) == 1 else 'rules differ'}. "
        f"{len(moved)} changed outcome."
    )
    lines.append("")

    for change in changes:
        lines.extend(_change_lines(change))

    return "\n".join(lines).rstrip() + "\n"


def _change_lines(change: RuleChange, heading: str = "##") -> list[str]:
    """One rule's movement, rendered.

    The heading level is a parameter because the same block sits under a `##`
    rule in a single-resource diff and under a `###` rule inside a `##`
    resource in a run-set diff. Everything below the heading is identical: a
    difference that read one way per resource and another way across a tenant
    would be two diffs.
    """
    lines = [f"{heading} {change.rule_id}", ""]

    if change.kind == "added":
        lines.append(f"New in this run: **{change.after.outcome.value}**.")
        lines.append("")
        lines.append(change.after.message)
        lines.append("")
        return lines
    if change.kind == "removed":
        lines.append(
            f"Present before as **{change.before.outcome.value}**, absent "
            f"now. A rule that stopped running is not a rule that passed."
        )
        lines.append("")
        return lines

    before_r, after_r = change.before, change.after
    if before_r.outcome is after_r.outcome:
        lines.append(f"**{after_r.outcome.value}**, unchanged.")
    else:
        lines.append(f"**{before_r.outcome.value} → {after_r.outcome.value}**")
    lines.append("")

    if change.rule_version_changed:
        lines.append(
            f"> **The rule changed too**, from v{before_r.rule_version} to "
            f"v{after_r.rule_version}. Part of this difference may be the "
            f"rule rather than the estate. Read the rule's changelog before "
            f"treating it as a finding."
        )
        lines.append("")

    if change.evidence:
        lines.append("Evidence that moved:")
        lines.append("")
        lines.append("| Path | Before | After |")
        lines.append("|---|---|---|")
        for ev in change.evidence:
            lines.append(f"| `{ev.path}` | {ev.before} | {ev.after} |")
        lines.append("")
    elif before_r.outcome is not after_r.outcome:
        lines.append(
            "No evidence value changed. The outcome moved for another "
            "reason: the rule, the profile, or which facts were collected."
        )
        lines.append("")

    lines.append(after_r.message)
    lines.append("")
    return lines


def regressions(changes: list[RuleChange]) -> list[RuleChange]:
    """The changes where a rule left `pass`.

    Leaving `pass` for anything else is losing an answer, whether the new
    outcome is `fail` or `unknown`. A pipeline that gates on regressions asks
    exactly this question.
    """
    return [
        c
        for c in changes
        if c.before
        and c.after
        and c.before.outcome is Outcome.PASS
        and c.after.outcome is not Outcome.PASS
    ]


# ---------------------------------------------------------------------------
# Many resources at once
# ---------------------------------------------------------------------------


@dataclass
class ResourceChange:
    """How one resource moved between two run sets."""

    resource_id: str
    display_name: str
    #: `added`, `removed`, `changed`, or `unchanged`.
    kind: str
    rules: list[RuleChange] = field(default_factory=list)


def _empty_run(resource: dict) -> Run:
    """A run with no results, to diff an added or removed resource against.

    `compare` reads only the results, so an empty one makes every rule on the
    other side read as added or removed, which is what a resource appearing or
    disappearing means.
    """
    return Run(results=[], provenance={}, coverage={}, resource=resource)


def compare_sets(before: RunSet, after: RunSet) -> list[ResourceChange]:
    old = {run.resource.get("id", ""): run for run in before.runs}
    new = {run.resource.get("id", ""): run for run in after.runs}

    out: list[ResourceChange] = []
    for rid in sorted(set(old) | set(new)):
        b, a = old.get(rid), new.get(rid)
        present = a or b
        name = present.resource.get("display_name") or present.resource.get("id", "?")
        if b is None:
            out.append(
                ResourceChange(rid, name, "added", compare(_empty_run(a.resource), a))
            )
        elif a is None:
            out.append(
                ResourceChange(rid, name, "removed", compare(b, _empty_run(b.resource)))
            )
        else:
            rule_changes = compare(b, a)
            out.append(
                ResourceChange(
                    rid, name, "changed" if rule_changes else "unchanged", rule_changes
                )
            )
    return out


def many_to_markdown(before: RunSet, after: RunSet) -> str:
    changes = compare_sets(before, after)
    added = [c for c in changes if c.kind == "added"]
    removed = [c for c in changes if c.kind == "removed"]
    moved = [c for c in changes if c.kind == "changed"]

    lines: list[str] = ["# What changed", ""]
    lines.append(f"- Resources before: {len(before.runs)}")
    lines.append(f"- Resources after:  {len(after.runs)}")
    lines.append("")

    if not (added or removed or moved):
        lines.append(
            "Nothing changed. Same resources, same outcomes, same rule versions."
        )
        return "\n".join(lines) + "\n"

    lines.append(
        f"{len(moved)} resources changed, {len(added)} added, {len(removed)} removed."
    )
    lines.append("")

    for change in changes:
        if change.kind == "unchanged":
            continue
        suffix = {"added": " (new resource)", "removed": " (resource gone)"}.get(
            change.kind, ""
        )
        lines.append(f"## {change.display_name}{suffix}")
        lines.append("")

        if change.kind == "removed":
            lines.append(
                "Present before, absent now. A resource that stopped being "
                "collected is not a resource that passed."
            )
            lines.append("")
            continue

        if change.kind == "added":
            findings = [
                rc
                for rc in change.rules
                if rc.after and rc.after.outcome is not Outcome.PASS
            ]
            if not findings:
                lines.append(
                    "New in this run. No findings: every rule passed or did not apply."
                )
                lines.append("")
            for rc in findings:
                lines.extend(_change_lines(rc, heading="###"))
            continue

        for rc in change.rules:
            lines.extend(_change_lines(rc, heading="###"))

    return "\n".join(lines).rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# the same comparison, as a model
# ─────────────────────────────────────────────────────────────────────────────
#
# Markdown was the only way out of here, which made this the one product
# surface a reader could not consume without parsing prose. Anything that had
# to know what changed would have had to re-derive it, and a second derivation
# of "what changed" is a second answer to the question the whole product is
# for.
#
# So the model comes first and the renderers are projections of it. The
# Markdown above is untouched: it is what a person reads, and this is what
# everything else reads.


def _change_to_dict(change: RuleChange) -> dict:
    """One rule's movement.

    `kind` is stated rather than left to be inferred from the two outcomes. A
    consumer working it out from `before` and `after` would be making the
    semantic decision this function exists to have already made, and two
    consumers would eventually disagree about it.
    """
    return {
        "rule_id": change.rule_id,
        "kind": change.kind,
        "rule_version_changed": change.rule_version_changed,
        # The full result on each side, in the same shape `evaluate --format
        # json` emits. A diff that summarised them would be a third
        # description of a result, and a consumer wanting the basis or the
        # sources would have to go and find the run again.
        "before": change.before.to_dict() if change.before else None,
        "after": change.after.to_dict() if change.after else None,
        "evidence": [
            {"path": e.path, "before": e.before, "after": e.after}
            for e in change.evidence
        ],
    }


def to_dict(before: Run, after: Run) -> dict:
    changes = compare(before, after)
    return {
        "diff_schema_version": "1.0",
        "scope": "run",
        "resource": {
            "id": after.resource.get("id") or before.resource.get("id", ""),
            "display_name": after.resource.get("display_name")
            or before.resource.get("display_name"),
        },
        "before_collected_at": before.provenance.get("collected_at"),
        "after_collected_at": after.provenance.get("collected_at"),
        # Counted here so no consumer has to count, and so every consumer
        # counts the same. `regressions` is the engine's own definition of a
        # rule that left `pass`, not an arithmetic anybody repeats.
        "counts": {
            "rules_differing": len(changes),
            "outcome_changed": sum(
                1
                for c in changes
                if c.before and c.after and c.before.outcome is not c.after.outcome
            ),
            "regressions": len(regressions(changes)),
        },
        "changes": [_change_to_dict(c) for c in changes],
    }


def many_to_dict(before: RunSet, after: RunSet) -> dict:
    resources = compare_sets(before, after)
    every = [rc for change in resources for rc in change.rules]
    return {
        "diff_schema_version": "1.0",
        "scope": "run-set",
        "counts": {
            "resources": len(resources),
            "resources_changed": sum(1 for r in resources if r.kind != "unchanged"),
            "rules_differing": len(every),
            "regressions": len(regressions(every)),
        },
        "resources": [
            {
                "resource": {"id": r.resource_id, "display_name": r.display_name},
                "kind": r.kind,
                "changes": [_change_to_dict(c) for c in r.rules],
            }
            for r in resources
        ],
    }


def to_json(before: Run, after: Run) -> str:
    return json.dumps(to_dict(before, after), indent=2, ensure_ascii=False) + "\n"


def many_to_json(before: RunSet, after: RunSet) -> str:
    return json.dumps(many_to_dict(before, after), indent=2, ensure_ascii=False) + "\n"
