# Trust model

This is not a technical document. It is the constitution of this repository.

If the collectors are rewritten in another language, if the evaluation engine
is replaced, or if the APIs behind the evidence change entirely, this document
must remain true word for word. That is the test it has to pass, and it is the
reason it names no product, no language and no API.

---

## First principle

> **Every governance conclusion must declare what kind of truth it is.**

Governance reports often present requirements, recommendations, conventions
and opinions with identical visual weight. A reader cannot tell which
statements they are free to disagree with.

This project does not do that. Every rule explicitly declares the nature of
the claim it makes.

---

## Second principle

> **Automation may verify a claim. It may never strengthen it.**

Automation may verify that:

- evidence exists;
- required sources are present;
- schemas are valid;
- documentation links resolve;
- conclusions are reproducible.

Automation must never infer:

- that a recommendation is a requirement;
- that a convention becomes documented guidance because it has a link;
- that missing evidence means compliance.

---

## Rule classification

Every rule declares:

```yaml
basis:
```

Permitted values:

```
requirement
documented-limit
documented-guidance
convention
opinion
```

This field is mandatory. Its value is never inferred.

---

## The obvious trap

A source does **not** imply a requirement.

This reasoning is intentionally invalid:

```
source exists
      ↓
therefore documented
      ↓
therefore requirement
```

A recommendation may cite documentation. An opinion may cite documentation. A
convention may cite documentation.

**The source explains the rule. It does not change its nature.**

The trap is attractive because it removes a field: if a source is present, why
not derive the classification from it? Anyone arriving at this repository
later will read that as a harmless simplification. It is the opposite. It
silently promotes an opinion with a link into a requirement, and every test
stays green while it happens.

---

## When a source stops resolving

Documentation moves. Over the life of a rule, some sources will die.

A dead link changes nothing about the nature of a rule. A `requirement` whose
source no longer resolves does not become a `convention`, and it does not
become stronger for having once been documented. It becomes a rule whose
evidence of authority needs repair.

Link rot is reported as a defect in the rule, never as a change to its
classification. The rule may still be evaluated, but reports must disclose
that its authority source could not be verified at the time of execution.

So the rule is not deleted and its `basis` is not lowered, and at the same
time a requirement whose source no longer resolves is not presented with the
same confidence as one whose source was verified.

---

## Review

The classification is intentionally visible in pull requests.

Changing

```
convention
```

to

```
documented-guidance
```

is not metadata. It changes the meaning of every report the rule appears in.

Reviewers are expected to challenge classification as carefully as
implementation. A pull request that changes a `basis` and explains only the
code has not been reviewed.

---

## Unknown

Unknown is a valid result.

Unknown is preferable to a false pass.

Evidence that was not collected must never become compliance.

Unknown is a result of insufficient evidence, not a lower severity of failure
and not a temporary pass. Reports and dashboards must not render it as an
amber "nearly compliant": it is the absence of an answer, not a weak one.

---

## Responsibility

Four responsibilities, and they are deliberately held apart:

| Responsibility | Held by |
|---|---|
| Collecting facts | the collectors |
| Evaluating rules against those facts | the engine |
| Guaranteeing structure | the schemas |
| Classifying the nature of a rule | **the author** |

The engine never classifies evidence.

The last row is the only one that is not automated, and that is deliberate.
Classification is an editorial judgement, and it belongs in a diff where a
human can contest it.

---

## Why this exists

Most governance tools answer:

> Is this compliant?

This project answers first:

> What kind of statement am I making?

Only then does it evaluate compliance.
