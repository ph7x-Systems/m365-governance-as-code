# Why these constraints exist

**All six are implemented.** This document is the reasoning behind them, kept
because the reasoning is the part that does not survive in a schema file.

Each was argued through before it was written, while the project was waiting on
a review exercise that has since been dropped in favour of feedback from people
using the tool. The argument outlived the exercise.

---

## 1. `RULE-REVIEW.md` said "the rule file", singular

Reviewers receive two rules, of deliberately different natures: one
`documented-limit`, one `convention`. Part of what the test measures is
whether a reviewer notices they are different kinds of claim without being
told that categories exist. With a single rule that half of the test
disappears.

Wording only. The protocol was always two, and it now says so.

---

## 2. Question 8: entailment

Added to the seven. It was held back while the review exercise was live,
because a reviewer told in advance to look for entailment defects is no longer
evidence that the rule leads them there:

> For each factual claim in each outcome message, name the condition and the
> evidence fields that make it necessarily true. If no such path exists, the
> message is invalid.

Its scope narrows once item 3 exists: interpolated values (`{items.count}`)
come from the evidence by construction. What needs a human is **prose claims
that are not interpolations** — normally one or two sentences per rule.

---

## 3. `required` equals the dependency set

The schema constrained one direction only: a condition may reference only
declared evidence. The inverse was missing, and it is the more useful one.
It now lives in the semantic validator, as `unused-required-evidence` and
`undeclared-dependency`.

```
dependencies = condition ∪ applicability ∪ interp(pass) ∪ interp(fail)
required     = dependencies
```

Both inequalities are errors, for different reasons:

- **`required` ⊃ dependencies** — a mandatory field nobody reads. It
  manufactures `unknown` on resources the rule could have decided, because a
  fact that was not collected produces `unknown` whether or not anything
  consumes it. `unknown` is expensive by design: it never aggregates as a
  pass, it has to be explained in the report, and it sends someone to
  investigate a collection that was never needed. It also creates false
  coherence for a reader, who sees a field named next to a message and takes
  proximity for proof.
- **`required` ⊂ dependencies** — the rule decides using something it never
  declared.

This makes `required` a property of the rule's dependency graph rather than
an attribute of a field. It says *"without this, the rule cannot decide"*,
not *"it would be good to have this"*.

Declared-but-unused optional evidence is an error too, on the false-coherence
ground alone. If every declared field must be consumed, and every consumed
field is required, then optional evidence has no role in this version.
Purely explanatory evidence may deserve a concept of its own later; it does
not get one as a generic escape hatch.

---

## 4. No interpolation in the three failure messages, enforced by the schema

```
interp(unknown | not_applicable | invalid_evidence) = ∅
```

Those messages are printed precisely when the evidence is missing, out of
scope, or malformed. A field cannot be both the reason the rule could not
decide and a value the rule prints. This is not fragility, it is a
contradiction: the message breaks in the only case it was written for.

Both existing rules already comply, without the constraint having been
stated. That is the argument for writing it down — it survives to whoever
writes the tenth rule.

---

## 5. `required: true` stays in the YAML, and the schema pins it

Item 3 makes it derivable. Remove it anyway and the engine starts deciding
what a rule depends on.

It stays for the same reason `basis` is declared instead of inferred from the
presence of a source: the author asserts, the schema proves. A redundant
field that gets validated is not noise — the declaration stays visible in a
diff, and a divergence between what the author believed the rule needed and
what it actually consumes becomes a readable error instead of a silent
inference.

The difference is between a validator saying *"you declared a required field
that nothing reads"* and an engine quietly knowing better than the author.
The second is what the trust model exists to prevent.

---

## 6. Done: the entailment defect is fixed and kept

`SPO-LIST-001` carried a defect where the `fail` message asserted a conjunction
the condition never established. It was left in deliberately, as an exercise
for a review that has since been dropped.

The rule in `rules/` is version 2.0 and correct. Version 1.0 is kept, with the
defect intact and explained, in [review/packet/](review/packet/), because it is
the clearest example in the repository of the failure this project exists to
prevent.

Item 3 above is what now catches it mechanically, and `m365-governance
validate` rejects version 1.0 on those grounds.

---

## Order

All six are implemented. The formal JSON Schema mentioned when this document was written now exists, in
[../schemas/](../schemas/), together with the validator that enforces the
constraints JSON Schema cannot express. See
[JSON-SCHEMA-PLAN.md](JSON-SCHEMA-PLAN.md) for which layer owns what.
