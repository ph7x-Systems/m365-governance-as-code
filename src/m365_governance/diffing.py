"""Comparing two runs.

The question a periodic audit actually asks is not "what is wrong today" but
"what changed, and was it the estate or was it us".

Both halves matter, so a diff reports the rule version alongside the outcome.
A result that moved because somebody edited the rule is not a result that
moved because somebody removed an owner, and a comparison that cannot tell
them apart is worse than no comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .results import EvidenceUsed, Outcome, Result, Run

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
        lines.append(f"## {change.rule_id}")
        lines.append("")

        if change.kind == "added":
            lines.append(f"New in this run: **{change.after.outcome.value}**.")
            lines.append("")
            lines.append(change.after.message)
            lines.append("")
            continue
        if change.kind == "removed":
            lines.append(
                f"Present before as **{change.before.outcome.value}**, absent "
                f"now. A rule that stopped running is not a rule that passed."
            )
            lines.append("")
            continue

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

    return "\n".join(lines).rstrip() + "\n"
