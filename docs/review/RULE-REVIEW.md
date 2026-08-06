# Reviewing a rule

Used twice: once as the acceptance test for the model itself, and afterwards
as the checklist for every pull request that adds or changes a rule.

---

## The test of the model

Two reviewers, given **only** the two rule files and
[BASIS.md](BASIS.md). Nothing else: no architecture, no engine, no
explanation of the project.

Two rules, not one, and of deliberately different natures: one
`documented-limit`, one `convention`. Half of what this measures is whether a
reader notices they are different kinds of claim without being told that
categories exist. With a single rule that half disappears.

- one who works with Microsoft 365 day to day;
- one from governance, risk or audit who does not write code.

Both needed. If only the technical reviewer can work with it, the model is
still too close to the code. If only the governance reviewer can, it lacks
operational precision.

---

## The seven questions

Answered in writing, by each reviewer, separately.

1. What claim is this rule making?
2. Is the chosen `basis` right or wrong, and why?
3. Does the severity feel inevitable, or arguable?
4. What evidence would make this rule pass, fail, or be unknown?
5. Before reading `limitations`: in what situation would this rule pass
   without the risk being resolved? Then read the rule's own answer in
   `passes_without_resolving`. Is it the same one? Is it weaker than yours?
6. Which limitation is missing, or badly worded?
7. Would you change the rule, the profile, or the collector? Why?
8. For each factual claim in each outcome message, name the condition and the
   evidence fields that make it necessarily true. If no such path exists, the
   message is invalid.

Question 8 has a narrow target, and knowing that makes it quick. Interpolated
values such as `{items.count}` come from the evidence by construction, and the
validator already proves that every declared field is consumed. What needs a
person is the **prose claims that are not interpolations**, normally one or two
sentences per rule. Read those, and only those, against the condition.

Question 5 is asked in two halves on purpose. The rule now carries a written
answer, so a reviewer who reads it first cannot help agreeing with it. Answer
first, read second, and record both. A reviewer who finds a way the rule
passes that the author did not is the single most valuable output of this
test.

---

## What passing looks like

**The criterion is not agreement. It is disagreeing in the right place.**

It passes when a reviewer:

- argues with the `basis` without mentioning the engine;
- argues with the severity without touching the condition;
- names a limitation without asking to see code;
- understands what `unknown` is for;
- can tell a rule from a profile;
- does not try to put collection logic inside the condition.

It fails when the first question is *"but how does the engine calculate
this?"*, or when a reviewer cannot see where the evidence stops and the
recommendation starts.

Question 5 is the one that matters most. A reviewer who can describe how the
rule passes while the risk survives has understood both the rule and its
limits, which is the whole point of the exercise.

---

## What to record

Only these, and only what both reviewers produced independently:

- questions **both** of them asked;
- fields the two interpreted differently;
- statements that read as stronger than they were meant to be;
- places where either looked for information in the wrong file.

**Do not redesign the model from a single preference.** One reviewer disliking
a word is taste. Two reviewers reading the same field differently is an
ambiguity, and ambiguity is the only thing this test is looking for.

```markdown
## Review of <rule id>, <date>

Reviewers: <technical> · <governance>

### Asked by both

### Read differently

### Read as stronger than intended

### Looked for in the wrong place

### Change made, or reason for making none
```

---

## After the test

If both rules pass, the formal JSON Schema is written, and every decision
already documented becomes a validation error.

If either fails, the fix belongs in these documents. Writing the schema first
would freeze the ambiguity into code.
