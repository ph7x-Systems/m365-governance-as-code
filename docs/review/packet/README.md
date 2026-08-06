# A rule with a defect in it, on purpose

`SPO-LIST-001.yaml` in this directory is **version 1.0, and it is wrong**. The
version in `rules/` is 2.0 and is correct. This copy is kept because the
mistake in it is the most instructive thing in the repository.

Do not copy these files into `rules/`. The validator would reject one of them,
which is the point.

---

## The defect

```
declared     permissions.hasUniqueRoleAssignments, as required evidence
condition    items.count > 100000                  and nothing else
fail message "...above the limit, AND STILL INHERITS ITS PERMISSIONS"
```

The message asserts a conjunction the rule never established. A list that
already has unique permissions fails this rule, with a sentence about it that
is false.

It is not a defect of `basis`, of severity, or of a missing limitation. It is
a defect of **entailment**: the prose says more than the condition knows.

There is a second cost, and it is the one that surprises people. The unused
required field manufactures `unknown`: if a collector cannot return
`hasUniqueRoleAssignments`, the rule reports "we could not decide" on a list
whose item count was collected and would have decided it.

---

## Why it is here

It was written this way as an exercise: hand somebody the two rules and
`BASIS.md`, nothing else, and see whether the model leads them to it.

Reading top to bottom, it does not. The declared field appears just above the
message, the reader recognises the same words in both places, and proximity
reads as proof. Finding it means reading against the grain of the document,
from the message back to the condition.

That is why the repository now enforces it mechanically instead of relying on
a careful reader:

```
required == condition ∪ applicability ∪ interp(pass) ∪ interp(fail)
```

Evidence declared as required and consumed by none of those is a schema error.
`m365-governance validate` rejects version 1.0 for exactly that reason. Try it.

---

## The fix

Version 2.0 does not delete the field. It uses it: an `applicability` of
`permissions.inheritance_broken equals false` means the rule speaks only about
containers that still inherit, so the sentence in the message is now something
the rule established.

That also turns a false `pass` into an honest `not-applicable` for a container
that already has unique permissions, which is a different line in a report and
a truthful one.
