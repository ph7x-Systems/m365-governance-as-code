# Contributing

Rules are the interesting contribution. The engine is small on purpose and
will stay that way; the value of this project is a growing set of checks whose
claims are honest about what kind of claim they are.

---

## Before you start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . && pip install -r requirements-dev.txt

m365-governance validate     # every rule, every layer
pytest                       # the suite
python tools/examples.py --check
coverage run -m pytest && coverage report
```

Coverage has a floor rather than a target. It moves up when something real
gets covered, and never down to accommodate a change that stopped testing
something.

All of it runs offline. No tenant is needed to contribute a rule.

---

## Writing a rule

Start from [rules/sharepoint/SPO-SITE-001.yaml](rules/sharepoint/SPO-SITE-001.yaml),
which is short, and read [docs/RULE-SCHEMA.md](docs/RULE-SCHEMA.md) once.

Three things decide whether a rule gets merged, and none of them is whether
we agree with it.

**The `basis` is honest.** Five kinds, and the source never decides the type.
An opinion that cites Microsoft documentation is still an opinion. If you
label a convention as a requirement, the pull request will be about that and
nothing else.

**`passes_without_resolving` is answered.** Every rule states, in writing, how
it can pass while the problem survives. It is a field of its own because it is
the one authors skip. If you cannot answer it, the rule is not understood well
enough yet, and that is a useful thing to discover before the review.

**The messages claim only what the rule established.** If the `fail` message
says "and still inherits its permissions", the rule has to have checked that.
The validator catches evidence declared and never consumed, which is where
this usually starts, but the sentence itself is on you.

The build fails, deliberately, when `basis` is missing, when a documented type
has no source, when a convention has no rationale, when the condition reads
evidence nobody declared, when evidence is declared and never consumed, when a
failure message interpolates a value that is missing precisely when that
message prints, when a YAML key is duplicated, when two rules share an id, or
when any unknown field appears anywhere.

That last one is `additionalProperties: false` everywhere. `severty: high`
must stop the build, not disappear.

---

## Reviewing a rule

[docs/review/RULE-REVIEW.md](docs/review/RULE-REVIEW.md) is the checklist, and
its criterion is worth repeating here:

> **The test is not agreement. It is disagreeing in the right place.**

Argue with the `basis` without mentioning the engine. Argue with the severity
without touching the condition. Name a missing limitation without asking to
see code. A review that opens with *"but how does the engine calculate this?"*
means the rule has not been written clearly enough yet.

---

## Changing an existing rule

Read [docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md). The test is one sentence:

> If a report produced yesterday would be interpreted differently today, the
> rule version must change.

Removing a limitation is a breaking change, and it is the one that looks like
it is not. A limitation is the boundary of the claim; deleting one widens the
claim without touching the condition.

---

## Collectors

A collector observes. It never returns `is_compliant`, `risk`, `score` or a
recommended action, because a collector that judges has moved the judgement
out of a reviewable diff and into code.

It never returns an empty list in place of an error, and never presents a
truncated response as a complete one. Those two are how this model fails in
practice, and neither looks like a decision when it is written: one is a
`catch` that returns `@()`, the other is a loop that stops at the first page.

Read-only, always. CI parses the PowerShell and fails on any mutating verb.

---

## Pull requests

One rule, or one coherent change, per pull request.

Say what kind of claim you are adding and why you classified it that way. That
sentence is the review.

Commit messages: what changed and why it matters, in prose, without a prefix
convention. If a commit needs a bullet list to be understood, it is probably
two commits.

---

## Support the project

This project is developed independently.

If it has saved you time or helped your organisation, you can support future
development: [buymeacoffee.com/jtlivio](https://buymeacoffee.com/jtlivio)

Contributing a rule is worth more than a coffee, and neither is expected.

---

## What we will decline

- automatic remediation, in any form, including a flag that only suggests it;
- a rule that executes code;
- inferring `basis` from the presence of a source;
- treating missing evidence as compliance, anywhere, for any reason.

Those four are the project. Everything else is open.
