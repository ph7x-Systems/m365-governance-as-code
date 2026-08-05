# Changes waiting on the review

Decided, not applied. Every item here is blocked on the same thing: two
independent reviews of the two rules, described in
[review/RULE-REVIEW.md](review/RULE-REVIEW.md).

Nothing on this list may be applied before those reviews exist. Some items
would change what the reviewers see; the rest would change the checklist they
answer. Either way, applying them first turns the test into a rehearsal.

---

## 1. `RULE-REVIEW.md` says "the rule file", singular

Reviewers receive two rules, of deliberately different natures: one
`documented-limit`, one `convention`. Part of what the test measures is
whether a reviewer notices they are different kinds of claim without being
told that categories exist. With a single rule that half of the test
disappears.

Wording only. The protocol was always two.

---

## 2. Question 8: entailment

To be added to the seven, after the test and not before:

> For each factual claim in each outcome message, name the condition and the
> evidence fields that make it necessarily true. If no such path exists, the
> message is invalid.

It is held back because a reviewer told in advance to look for entailment
defects is no longer evidence that the rule leads them there. What the test
measures is whether the model produces the question on its own.

Its scope narrows once item 3 exists: interpolated values (`{items.count}`)
come from the evidence by construction. What needs a human is **prose claims
that are not interpolations** — normally one or two sentences per rule.

---

## 3. `required` equals the dependency set

Today the schema constrains one direction only: a condition may reference
only declared evidence. The inverse is missing, and it is the more useful
one.

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

## 4. No interpolation in the three failure messages

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

## 5. `required: true` stays in the YAML

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

## 6. One finding recorded outside this repository

There is a decision about the two rules that depends on how the reviewers
reach it, or whether they reach it at all. It is deliberately not written
here, because this repository is what gets handed over.

It is recorded out of band and will be brought back when the reviews are in.
If you are running the test and this paragraph is the first you hear of it,
that is the intended state: proceed with the seven questions as written.

---

## Order

1. two independent reviews;
2. compare the answers — questions both asked, fields read differently;
3. fix the ambiguities that both reviewers hit;
4. apply items 1 to 5;
5. resolve item 6;
6. only then write the formal JSON Schema.

Item 6 last on purpose. What it decides is not only *what* was found, but
**how** it was reached, and that is only visible once the answers exist.
