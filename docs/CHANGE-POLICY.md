# Change policy

This is not about Git. It is about what counts as a change of **meaning**.

A rule is read by people who compare reports over time. If a result moved
between two runs, they need to know whether the estate changed or the rule
did. That question has to be answerable from the rule version alone.

---

## The test

> **If a report produced yesterday would be interpreted differently today, the
> rule version must change.**

Everything below is that sentence applied.

---

## Breaking: the version changes

- changing `basis`, in either direction;
- changing the condition, its operator, or its threshold;
- changing `applicability`, which changes who the rule speaks about;
- **removing a limitation**, or narrowing `passes_without_resolving` so that
  the rule claims to cover a case it previously admitted it did not;
- changing the default severity;
- changing `evidence_requirements` in a way that alters what produces
  `unknown`.

Removing a limitation is on this list and looks like it does not belong. It
is the most dangerous entry. A limitation is part of what the rule claims: it
is the boundary of the claim. Deleting one silently widens the claim without
touching a single line of the condition, and every report from that moment
reads as stronger than the ones before it.

**Adding** a limitation is not breaking. It narrows a claim that was
previously overstated, which is a correction, not a redefinition.

---

## Non-breaking: the version stays

- correcting wording, grammar or formatting;
- adding an equivalent source alongside an existing one;
- repairing a URL that moved to the same content;
- clarifying a rationale without changing what it justifies;
- improving examples;
- adding a limitation.

The distinction in the URL case is exact: **repointing to the same content is
non-breaking; pointing to different content is a new claim.** A source that
now says something else is not a fixed link.

---

## Ambiguous, and how to decide

When it is unclear, ask what a reader of last week's report would conclude if
they read it again with today's rule in front of them. If they would revise
their reading, the version changes. If they would only find the same finding
better explained, it does not.

When it is still unclear after that, change the version. A version that moved
without needing to costs a line in a changelog. A version that should have
moved and did not costs the ability to compare, permanently, and nobody
notices until they are relying on the comparison.

---

## What the version is not

It is not a file version, and it is not a release number. Two rules that
changed on the same day carry unrelated versions. It describes the
**interpretation**, and nothing else.

---

## The schema has a version too, and it obeys the same test

A report is read through a rule. A rule is read through a schema. The schema
therefore participates in the meaning of every rule written against it, which
gives the governing test a second form, one level up:

> **A schema version changes when an existing rule could be interpreted
> differently without the rule itself changing.**

This is not a technical statement about file formats. A schema change that
alters what a field means is a semantic change to every rule in the
repository at once, and no rule version moves to record it. Without a schema
version in the run, that change is invisible in exactly the comparison the
policy above exists to protect.

So a rule declares which schema version it was written against, and a run
records both. See [JSON-SCHEMA-PLAN.md](JSON-SCHEMA-PLAN.md) for where the
version lives.

Adding a constraint the schema did not previously enforce is a schema change,
but not a semantic one: rules that already passed still mean what they meant.
Changing what an existing field is understood to say is semantic, and always
breaking.

---

## Deprecation

A rule is never silently deleted. Deleting one makes a finding disappear from
the next report with no explanation, which reads as the problem having been
resolved.

A withdrawn rule is marked as such, keeps its id forever, and states why it
was withdrawn: the limit moved, the product changed, the convention was
wrong. Ids are never reused.
