# Where each constraint lives

This document does not define the schema. It decides **where every rule about
a rule is enforced**, and why.

It exists because the boundary is easy to lose in both directions. Given a
constraint that JSON Schema cannot express, the temptation is to bend the
schema until it almost can. Given a validator that already exists, the
temptation is to move things into it that the schema was guaranteeing for
free. Both mistakes are cheap to make and expensive to find, because neither
produces a failure — they produce a constraint that is enforced twice, or
not at all.

---

## The principle

> **JSON Schema validates structure. It never evaluates meaning.**

And the operational half of it:

> **Every validation has exactly one owner.**

A constraint implemented in two layers will diverge. Not immediately: it
diverges the first time one of them is corrected. From then on the rule that
passes depends on which layer ran, and nobody notices until the two disagree
about a rule somebody cares about.

**Tie-break, when a constraint could live in more than one layer:** it
belongs to the **lowest layer that can express it completely**. Lower layers
run earlier, fail faster, and need less context to be understood. "Completely"
is the operative word — a layer that can express most of a constraint does not
own it, because the remainder would have to live somewhere else and that is
the divergence this rule prevents.

---

## The layers

Six, ordered by **scope**: one field, one file, every file, the outside
world, a person. Each one assumes the previous passed.

Scope is the axis on purpose. Cutting the layers by *kind of logic* —
structural, cross-referential, semantic — produces boundaries that move every
time somebody argues about which kind a constraint is. Scope does not move: a
constraint either needs a second file to decide or it does not.

**1. YAML parsing** — the file is a document at all.

Must reject duplicate keys explicitly. Most YAML parsers accept them and keep
the last, which in a governance rule means a `severity` silently overriding
another `severity`. This is a parser configuration decision, and it belongs
here rather than anywhere else because no later layer can see what was lost.

**2. JSON Schema** — one document, no outside knowledge.

Types, enums, required fields, string patterns, conditional requirements
(`if`/`then`), and `additionalProperties: false` everywhere. Anything that
can be decided by looking at a single rule file, without following a
reference, belongs here.

**3. Rule graph validator** — one document, references followed.

Everything that requires relating one part of a rule to another: the
condition to the evidence, the messages to the condition. Still a single
file, but no longer a single field.

**4. Repository validator** — all documents together.

Uniqueness and history: duplicate ids, reused ids, versions that moved
without a meaning change, withdrawn rules that vanished instead of being
marked.

**5. Source liveness** — the outside world.

Whether the URLs still resolve, and still say what the rule says they say.
**The only layer that is not deterministic**, and therefore the only one that
may not block a build the way the others do: a network failure is not a
defect in a rule. It runs as its own job, reports separately, and — per the
trust model — a dead source never alters `basis`. It is a defect in the rule,
disclosed in the report, not a downgrade of the claim.

**6. Human** — the judgements the model forbids automating.

A layer, not a footnote. Whether a source still supports the claim, whether a
`convention` is really a convention, whether a `passes_without_resolving` is
honest: these have an owner, they have a moment in the process, and they fail
review when they are skipped. Leaving them out of the list would suggest the
other five eventually cover everything, and they never will.

The layer boundary that matters most is between 2 and 3, and it is exactly
this: **layer 2 never follows a reference.**

---

## Decision table

| Constraint | Owner | Reason |
|---|---|---|
| `basis.type` is one of the five | 2 | Enum on one field |
| `basis` present | 2 | Required field |
| `severity.rationale` present | 2 | Required field |
| `passes_without_resolving` present and non-empty | 2 | Required field, `minLength` |
| Documented types carry ≥1 source | 2 | `if`/`then` on `basis.type`, `minItems` |
| `convention` and `opinion` carry a rationale | 2 | `if`/`then` on `basis.type` |
| `documented-limit` carries an explicit `limit` block | 2 | `if`/`then` on `basis.type` |
| `checked_at` present on every web source | 2 | Required field inside the source object |
| `checked_at` is a date, not a year or a phrase | 2 | `format: date` |
| All five outcome messages present | 2 | Required fields |
| `error` is not authorable | 2 | `additionalProperties: false` on `outcomes` |
| No interpolation in `unknown` / `not_applicable` / `invalid_evidence` | 2 | Purely lexical: those three strings may not contain `{`. See below |
| Unknown field anywhere | 2 | `additionalProperties: false` |
| Condition operator is one of the twelve | 2 | Enum |
| Condition references only declared evidence | 3 | Relates two parts of one file |
| `required == condition ∪ applicability ∪ interp(pass) ∪ interp(fail)` | 3 | Dependency graph of one file |
| Every interpolation names a real evidence path | 3 | Same graph |
| Duplicate rule id | 4 | Needs every rule |
| Reused id from a withdrawn rule | 4 | Needs history |
| Rule deleted rather than withdrawn | 4 | Needs history |
| Source URL resolves | 5 | Network |
| Source still says what the rule claims | 6 | No validator can prove a rule represents a document correctly |

Two rows deserve their reasoning.

The last one has an owner rather than a dash, and that is the point. Layer 5
can prove a URL exists, responds, is HTTPS and is not a 404. It can never
prove the rule represents the document correctly. That is the documentary
form of the founding principle — automation may verify a claim, never
strengthen it — and it is why the human layer is numbered like the others
instead of being described as what is left over.

**No interpolation in the three failure messages** looks like it belongs to
layer 3, since it is about the relationship between messages and evidence. It
does not. Expressed as *"these three strings may not contain `{`"* it needs no
reference-following at all, and by the tie-break it belongs to layer 2. The
constraint is lexical even though the reasoning behind it is semantic — and
the layer is decided by the constraint, never by the reasoning that produced
it.

---

## What layer 3 needs that layer 2 cannot give

Three functions, and they are the whole of it:

```
evidence_paths(rule)   → every path declared in evidence_requirements
referenced(rule)       → paths named by condition and applicability
interpolated(message)  → paths inside {...} in a message string
```

Everything in layer 3 is set arithmetic over those three. That is worth
stating because it bounds the layer: **layer 3 evaluates no conditions and
reads no evidence.** It never asks whether a rule would pass. It only asks
whether the rule is internally consistent, and it answers with no tenant, no
collector and no data anywhere near it.

---

## Schema versioning

The schemas are versioned independently of the rules, and the version lives
in `$id`. A rule declares which schema version it was written against.

The reason is [CHANGE-POLICY.md](CHANGE-POLICY.md) applied one level up: a
report is interpreted through a rule, and a rule is interpreted through a
schema. If the schema changes what a field means, every rule written before
that change is affected, and no rule version moved.

---

## Future work

Reserved, deliberately not designed here:

- **profiles** — which rules run, and with which severity overrides;
- **report schema** — the shape of the output, human and JSON;
- **execution snapshot schema** — what a run recorded about itself: rule
  versions, schema versions, collector identity, scope, and time.

The third one is the one to not forget. Without it a report is a set of
findings with no way to say which rules produced them, which is precisely the
comparison the change policy exists to protect.

---

## Blocked

Nothing here can be written as an actual schema until the review described in
[review/RULE-REVIEW.md](review/RULE-REVIEW.md) has happened and the items in
[POST-REVIEW-CHANGES.md](POST-REVIEW-CHANGES.md) are resolved. Two of those
items change what the schema must enforce.

This document is the map. It is not the implementation, and writing it early
is safe precisely because it commits to no field names.
