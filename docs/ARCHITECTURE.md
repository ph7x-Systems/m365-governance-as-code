# Architecture

This document fixes the boundaries between the parts. It is deliberately the
last of the four to be written: the boundaries only became clear after
[TRUST-MODEL.md](TRUST-MODEL.md), [RULE-SCHEMA.md](RULE-SCHEMA.md) and
[EVIDENCE-SCHEMA.md](EVIDENCE-SCHEMA.md) existed.

It names languages where it must, but every boundary here survives replacing
them.

---

## The shape

```
collectors  ─→  evidence  ─→  engine  ─→  results  ─→  reports
                   ▲            ▲
                schemas      rules + profile
```

Evidence flows one way. Nothing downstream writes back.

---

## The governing sentence

> **The engine reasons from what is known, not from whether collection was
> complete.**

An incomplete collection does not produce an unknown result. It produces a
result that may be unknown, if and only if the missing part could change it.

---

## Bounded evaluation

When evidence is incomplete but bounded, the engine reasons from the bounds.

For a numeric comparison against a threshold:

```
pass      if the lower bound already satisfies the condition
fail      if the upper bound already fails it
unknown   otherwise
```

Concretely: a site with three direct owners and one unexpanded group has
`minimum_count: 3` and no upper bound. Against `owners >= 2` the answer is
`pass`, proven. Against `owners >= 5` the answer is `unknown`, because the
unexpanded group could carry the difference. **Without an upper bound the
engine can prove `pass` and can never prove `fail`.**

This generalises past counting. Evidence that is incomplete is
*monotonic*: collecting more can add facts, never remove them. So each
operator has a side on which a partial answer is already final:

| Operator | Decidable from partial evidence when |
|---|---|
| `greater-than`, `greater-than-or-equal` | the lower bound satisfies it → `pass` |
| `less-than`, `less-than-or-equal` | the upper bound satisfies it → `pass` |
| `contains`, `in` | the known part already contains it → `pass` |
| `not-contains`, `not-in` | the known part already contains it → `fail` |
| `exists` | one instance is known → `pass` |
| `not-exists` | one instance is known → `fail` |
| `equals`, `not-equals` | never, unless the value is single and observed |

Everything not decidable is `unknown`. This table belongs here rather than in
each rule, because a rule author must not have to reason about partial
evidence: they declare the condition, and the engine decides what can be
concluded from what was collected.

---

## Derived paths

Almost every evidence path is read. One kind is computed, and the boundary
matters enough to be written down.

A rule asks for `owners.count`. The evidence does not contain that field: it
contains `expansion_complete`, and then either `effective_count` or
`minimum_count`, because a group owner is one principal and may be forty
people. The engine turns those into the quantity the rule asked for — an exact
value when the expansion completed, a lower bound when it did not.

**The engine may derive a fact the evidence schema defines, and may never
invent one.** The difference is testable: a derivation is a function of fields
that are present, it appears in the result next to the evidence it came from,
and it carries the state it was derived under. `at least 3` is printed as
`at least 3`, never as `3`.

Without this, a rule author would have to reason about partial expansion in
every rule that counts anything, and the first one to forget would report a
group of forty as one owner.

---

## Resolution order

Fixed, and not a choice the engine makes:

```
invalid-evidence  →  not-applicable  →  unknown  →  pass / fail
```

`invalid-evidence` is first so that a malformed value cannot vanish beneath an
applicability decision. An engine free to reorder could turn a broken
collector into a clean report.

---

## The five parts

### Collectors

They collect, normalise, expand groups, and compute factual bounds such as
`minimum_count`.

They never evaluate compliance, never assume a default for a fact they could
not read, never return an empty list in place of an error, and never present a
throttled or truncated response as complete.

Collectors are written in whatever speaks to the source most directly. Today
that is PowerShell, because the Microsoft 365 administrative surface is
reachable there with the least ceremony. That is an implementation choice; the
boundary is the JSON they emit, and it is the only thing the rest of the
system knows about them.

### Schemas

They validate shape and types.

They do not validate cross-field relationships that require semantic context.
A rule whose `condition` reads a path its `evidence_requirements` never
declared is invalid, and no JSON Schema expresses that. It belongs to the
validator, and the validator needs its own tests.

### Engine

It applies the resolution order, uses bounds where they exist, and returns
`unknown` only when the missing information could change the outcome.

**It never alters evidence.** Anything it derives lives in the result, next to
the evidence it was derived from, so a reader can see both.

It never classifies. `basis` is authored, and the engine's only relationship
with it is to carry it into the report unchanged.

### Rules

They declare a condition, a `basis`, a severity with its own rationale,
limitations, and a message per authorable outcome.

They execute no code. They infer no evidence. A rule that needs a script is a
rule whose evidence is not yet in the right shape, and the fix belongs in the
collector.

### Profiles

They select which rules run, and may parameterise thresholds and severity.

**They never duplicate or rewrite the meaning of a rule.** This is why rules
and profiles are separate directories from the first commit: the moment a rule
is copied to give one profile a different weight, two things happen that
cannot be undone cheaply. Results stop being comparable across profiles,
because they no longer answer the same question. And the `basis` gets
reviewed twice, in two files, which is how the two copies start to disagree.

One profile exists today, `default`. The second one is created when a concrete
rule needs to differ, not before.

---

## What this system does not do

It does not change anything in a tenant. There is no write path, no
remediation command, and no `--fix-all`. Remediation is text in a rule,
addressed to a person.

This is not caution about bugs. A tool that both judges and repairs stops
being auditable: the evidence for a finding is gone once the finding has been
acted on, and the report can no longer be reproduced against the state that
produced it.

---

## Open decisions

Recorded here so they are decided deliberately rather than by the first
commit that needs them:

- how a profile expresses a threshold override without restating the rule;
- whether results carry the full evidence or a reference to a stored snapshot;
- how rule versions appear in a comparison between two runs;
- what a report does with a rule whose source no longer resolves, beyond
  disclosing it.
