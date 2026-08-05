# Rule schema

This document defines what a rule is allowed to say, and therefore what the
engine is allowed to conclude. It is written before any JSON Schema, because
the semantics have to be settled first: a schema can only enforce a decision
that has already been made.

It is governed by [TRUST-MODEL.md](TRUST-MODEL.md). Where the two disagree,
the trust model wins.

---

## The golden rule

> **The schema must prevent a rule from appearing more certain than it is.**

Everything below follows from that sentence. When a field looks like
bureaucracy, this is the reason it exists.

---

## Fields

| Field | Required | Purpose |
|---|---|---|
| `id` | yes | Stable identifier. Never reused, never renumbered |
| `version` | yes | Changes when the **meaning** changes. See below |
| `title` | yes | One line, stated as the condition being checked |
| `description` | yes | What this rule is about, in prose |
| `service` | yes | The product area the rule belongs to |
| `resource_type` | yes | The kind of thing evaluated: a site, a group, an app |
| `basis` | yes | **The nature of the claim.** See below |
| `severity` | yes | Impact, independent of `basis`. See below |
| `applicability` | no | When the rule applies. Absent means always |
| `evidence_requirements` | yes | Exactly which facts the rule needs |
| `condition` | yes | The comparison that produces `pass` or `fail` |
| `outcomes` | yes | A message per authorable state |
| `remediation` | no | What to do about a failure |
| `limitations` | yes | What this check does **not** establish |

### On `limitations`

Not a list. A structure, with one mandatory field:

```yaml
limitations:
  passes_without_resolving: >
    Two dormant owners satisfy this rule and solve nothing.
  other:
    - >
      Where ownership is held by a group, the count depends on whether the
      collector expanded that group.
```

`passes_without_resolving` answers one question, and it is the hardest one to
ask about your own rule:

> **How can this rule pass while the problem survives?**

It is a separate field rather than one entry among others because it is the
one that gets omitted. An author who cannot answer it has not yet understood
what the rule measures, and the most common failure in governance is exactly
this gap: **complying with the policy is not the same as reducing the risk.**

A rule with no honest answer here is a rule that should not be written yet.

`other` may be empty. `passes_without_resolving` may not.

### On `version`

The version changes when the meaning changes: the condition, the threshold,
the applicability, or the `basis`. It does not change for wording.

This matters because reports are compared over time. A result that improved
between two runs may have improved because the estate changed, or because the
rule did. Both runs carry the rule version so the difference can be told
apart.

---

## `basis`

Not a string. A structure, because a classification without its justification
is an assertion.

```yaml
basis:
  type: documented-guidance
  sources:
    - url: https://learn.microsoft.com/...
      title: Manage sharing settings
      publisher: Microsoft
      checked_at: 2026-08-05
  rationale: >
    Microsoft documents this as recommended configuration. It is not enforced
    by the product, and a tenant may legitimately decide otherwise.
```

**Rules:**

- `requirement`, `documented-limit` and `documented-guidance` require at least
  one source;
- `convention` and `opinion` require a `rationale`; a source is optional;
- `checked_at` is mandatory on every web source;
- **a source never determines the type.** See the trap in the trust model;
- a dead source does not alter `type`. It is reported as a defect in the rule,
  and reports disclose that the authority could not be verified.

`documented-limit` carries one more obligation: the limit itself is stated in
the rule, next to the observed value, so a reader can see both numbers without
following the link.

---

## `severity`

Independent of `basis`, and this separation is deliberate.

```yaml
severity:
  default: medium
  rationale: >
    Losing the only accountable owner commonly delays access and
    administration decisions, but no data is exposed by it.
  configurable: true
```

**Severity must never be derived from `basis`.** They are different axes:

- a `requirement` may have low impact;
- a `convention` may protect against a critical risk.

A consumer changing `severity` is expressing a different appetite for risk. A
consumer changing `basis` is contradicting a statement about the world. The
first is configuration. The second is an argument, and belongs in a pull
request.

---

## `applicability`

Decides whether the rule speaks at all about a given resource. It uses the
same grammar as `condition`.

When applicability is not met, the outcome is `not-applicable`. That is not a
pass, and reports must not aggregate it as one: a rule that never applied has
established nothing.

---

## `evidence_requirements`

Each rule declares exactly which facts it needs, and their type.

```yaml
evidence_requirements:
  - path: owners.count
    type: integer
    required: true
```

This is what makes the difference between four distinct outcomes
mechanically decidable instead of a matter of interpretation:

| Situation | Outcome |
|---|---|
| A required fact was not collected | `unknown` |
| A fact was collected with the wrong type | `invalid-evidence` |
| The resource is out of scope for the rule | `not-applicable` |
| The condition was evaluated | `pass` or `fail` |

**The condition may only reference declared evidence.** A condition reading a
path that `evidence_requirements` does not declare is a schema error, not a
runtime surprise. This is a cross-field constraint and cannot be expressed in
JSON Schema alone: it belongs to the validator, and it needs its own test.

---

## `condition`

A small grammar, deliberately. Not a language.

```yaml
condition:
  operator: less-than
  evidence: owners.count
  value: 2
```

### A true condition is a failure

> **The condition describes the state being reported. Finding it is `fail`.**

`owners.count less-than 2` and `items.count greater-than 100000` both name the
case worth reporting, not the case worth approving. A rule author writes the
problem, never the health.

This is stated because it is the one thing about a rule that cannot be read
off the file. Both readings are defensible in the abstract, and a rule written
under the opposite assumption inverts every result it produces without failing
any validation: the schema, the graph and the messages all still hold. A
reviewer would have to infer the direction from the prose of the messages,
which is exactly the kind of inference this model exists to remove.

### No composition

There is no `and`, no `or`, and no nesting. One operator, one evidence path,
one value.

Where two facts must both hold, one of them belongs in `applicability`: it
decides whether the rule speaks about the resource at all, and the condition
then decides the one question that remains. `SPO-LIST-001` is exactly this
shape — it applies only to containers that still inherit permissions, and asks
only about the count.

That split is usually better than a conjunction, because it produces
`not-applicable` where a conjunction would produce `pass`. A container that
already has unique permissions did not satisfy the rule; the rule had nothing
to say about it, and those are different report lines.

Composition is added when a real rule appears that cannot be expressed as
applicability plus condition — not before, and not because one would read more
naturally.

Permitted operators in the first version:

```
equals                    not-equals
less-than                 less-than-or-equal
greater-than              greater-than-or-equal
contains                  not-contains
exists                    not-exists
in                        not-in
```

**No embedded code, no arbitrary expressions, no scripts inside rules.**

This is not a limitation to be lifted later when a rule gets hard. A rule that
needs a script is a rule whose evidence is not yet in the right shape, and the
fix belongs in the collector. The moment rules can execute, they stop being
reviewable by anyone who does not read the language they execute in, and the
classification stops being contestable in a diff.

---

## `outcomes`

A message per state that a **rule** can produce:

```yaml
outcomes:
  pass:
    message: ...
  fail:
    message: ...
  unknown:
    message: ...
  not_applicable:
    message: ...
  invalid_evidence:
    message: ...
```

All five are required. A state without a message would be reported as a bare
label, and a bare label is exactly the green box this project exists to avoid.

**`error` is not here, and that is on purpose.** `error` means the evaluation
did not finish: a bug, a crash, a malformed rule. It is a statement about the
engine, not about the resource, so a rule may not author its message. A rule
that could describe its own failure would be describing something it cannot
observe.

---

## What the schema must reject

The schema fails, and CI fails with it, when:

- `basis` is missing;
- a documented type (`requirement`, `documented-limit`, `documented-guidance`)
  has no source;
- a `convention` or `opinion` has no rationale;
- `severity` has no rationale;
- a web source has no `checked_at`;
- the condition references evidence that was not declared;
- any of the five outcomes has no message;
- `limitations` is missing, or `passes_without_resolving` is missing or empty;
- **any unknown field appears anywhere.**

The last one is `additionalProperties: false` on every structural object, and
it is not pedantry. A misspelt field in a governance rule that is silently
ignored produces a rule that looks complete and is not. `severty: high` must
stop the build, not disappear.

---

## Next

Two complete rules, written by hand, before any engine exists:

- one `documented-limit`;
- one `convention`.

If both are readable, contestable in a pull request, and impossible to
confuse with each other, the model is ready to be turned into a formal schema.
