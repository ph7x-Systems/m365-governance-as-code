# Evidence schema

## 1. Purpose

This document defines what a collector is allowed to hand to the engine, and
in what shape. It is the other half of the boundary that
[RULE-SCHEMA.md](RULE-SCHEMA.md) opens: rules declare what facts they need,
evidence declares what was actually observed.

It is governed by [TRUST-MODEL.md](TRUST-MODEL.md).

> **Missing evidence is a fact about collection, not a fact about the
> resource.**

Half of this document exists to make that sentence enforceable.

---

## 2. Principles

**Evidence is not conclusion.** A collector returns what it observed. It never
returns `is_compliant`, `risk`, `score`, `recommended_action`, or any field
that presumes a rule. A collector that judges has made the rule unreviewable,
because the judgement is now in code instead of in a diff.

**Provenance travels with the facts.** Two identical numbers gathered by
different methods, at different times, with different permissions, are not the
same evidence. Without provenance they look the same.

**Absence has a reason.** A value that is not present must say why it is not
present. `null` may not carry six meanings.

**Evidence is a snapshot.** The engine derives results from evidence and never
writes back into it. Anything the engine computes belongs in the result.

---

## 3. Common envelope

Every evidence document, whatever the resource, has the same outer shape:

```yaml
schema_version: 1.0
provenance: { ... }
coverage: { ... }
resource: { ... }
facts: { ... }
```

`facts` is the only part that varies by resource type. Everything else is
identical so that a report can describe how any evidence was gathered without
knowing what it is about.

---

## 4. Provenance

```yaml
provenance:
  collected_at: 2026-08-05T14:02:11Z
  collector: spo-site-collector
  collector_version: 1.0.0
  source_system: SharePoint Online
  source_api: Microsoft Graph v1.0
  tenant_id: 00000000-0000-0000-0000-000000000000
  identity_kind: application            # application | delegated
  scopes:
    - Sites.Read.All
```

`identity_kind` and `scopes` are recorded because they change what could be
seen. A delegated run sees what one person sees, and a report built from it
must not be read as a tenant-wide statement. This field is the difference
between a partial audit and a misleading one.

---

## 5. Collection states

Every fact carries a state. The permitted values:

| State | Meaning |
|---|---|
| `observed` | The value was read from the source |
| `missing` | The source was reached and returned nothing for this fact |
| `not-supported` | The source does not expose this fact at all |
| `permission-denied` | The identity used was not allowed to read it |
| `partial` | Some of the value was read, and it is known to be incomplete |
| `invalid` | A value came back that does not fit its declared type |

`missing` and `not-supported` are deliberately different. The first may be
fixed by looking again; the second never will, and a rule that depends on it
is not applicable to this source rather than unresolved.

`permission-denied` is separate from both because it is the only one whose fix
is a decision by a human about access, and because it is the state most often
laundered into "no data, therefore fine".

### `[]` is not absence

An empty list means **observed, and there are none**. A fact that was not
collected is not an empty list, and a collector that returns `[]` on failure
has destroyed the distinction the whole model rests on.

---

## 6. Coverage

Provenance says how. Coverage says how much.

```yaml
coverage:
  requested: [owners, sharing, permissions]
  completed: [owners, permissions]
  unavailable:
    sharing:
      state: permission-denied
      detail: The identity lacks Sites.FullControl.All
```

A report may not treat a fact absent from `completed` as absent from the
resource. The blocks a rule needs and coverage did not deliver produce
`unknown`, and `unknown` is rendered as the absence of an answer.

---

## 7. Facts: raw and normalised

Collectors receive names chosen by the API, not by us. Both are kept:

```yaml
facts:
  permissions:
    inheritance_broken:
      value: true
      state: observed
      raw:
        field: hasUniqueRoleAssignments
        value: true
```

The normalised name is what rules reference and what survives an API rename.
The `raw` block is what lets someone reproduce the observation against the
source, which is the difference between a finding and an assertion.

`hasUniqueRoleAssignments` is collected as an observed fact. **The engine never
infers it** from a list of permissions, because a permission list that was
truncated, throttled or partially denied would produce a confident and wrong
answer.

---

## 8. Expansion, and when incomplete evidence still decides

Counting owners is where a naive schema quietly lies. A group owner is one
principal and may be forty people.

```yaml
facts:
  owners:
    state: observed
    direct:
      - principal_id: 7c1f...
        principal_type: user
    groups:
      - principal_id: 9ab2...
        principal_type: group
        expansion:
          status: complete        # complete | incomplete | not-attempted
          member_count: 3
    expansion_complete: true
    effective_count: 4
```

**When expansion is incomplete, `effective_count` is absent.** In its place:

```yaml
    expansion_complete: false
    minimum_count: 3
```

`minimum_count` is what is known for certain: the direct owners plus the
groups that were expanded. It matters because **incomplete evidence sometimes
still decides the rule**.

A site with three direct owners and one unexpanded group has
`minimum_count: 3`. A rule asking for at least two owners can answer `pass`
from that, with certainty, and returning `unknown` there would be a different
kind of wrong: refusing to answer a question the evidence does answer.

The engine returns `unknown` only when the outcome depends on what was not
collected. That is a property of each comparison, not of the evidence, and it
belongs to the engine.

---

## 9. Example: a complete site

```yaml
schema_version: 1.0
provenance:
  collected_at: 2026-08-05T14:02:11Z
  collector: spo-site-collector
  collector_version: 1.0.0
  source_system: SharePoint Online
  source_api: Microsoft Graph v1.0
  tenant_id: 00000000-0000-0000-0000-000000000000
  identity_kind: application
  scopes: [Sites.Read.All]
coverage:
  requested: [owners, permissions]
  completed: [owners, permissions]
  unavailable: {}
resource:
  id: contoso.sharepoint.com,7c1f...,9ab2...
  type: site
  display_name: Finance
  url: https://contoso.sharepoint.com/sites/Finance
facts:
  owners:
    state: observed
    direct:
      - { principal_id: 7c1f..., principal_type: user }
      - { principal_id: 4d8e..., principal_type: user }
    groups: []
    expansion_complete: true
    effective_count: 2
```

## 10. Example: partial

```yaml
coverage:
  requested: [owners, sharing]
  completed: [owners]
  unavailable:
    sharing:
      state: permission-denied
      detail: The identity lacks the scope required to read sharing settings
facts:
  owners:
    state: observed
    direct: [ { principal_id: 7c1f..., principal_type: user } ]
    groups:
      - principal_id: 9ab2...
        principal_type: group
        expansion: { status: not-attempted }
    expansion_complete: false
    minimum_count: 1
```

A rule about sharing returns `unknown` here. A rule asking for at least two
owners also returns `unknown`, because `minimum_count: 1` does not settle it:
the unexpanded group might contain the second owner.

## 11. Example: invalid

```yaml
facts:
  items:
    count:
      state: invalid
      raw: { field: ItemCount, value: "many" }
      detail: Expected integer
```

The rule returns `invalid-evidence`, not `unknown`. The distinction matters
because the fix is different: `unknown` is fixed by collecting again,
`invalid-evidence` is fixed by repairing the collector or the schema.

---

## 12. Relationship to rules

A rule's `evidence_requirements` name paths into `facts`. The engine resolves
each one and decides in this order:

1. any required path in `invalid` state → `invalid-evidence`;
2. `applicability` evaluates false → `not-applicable`;
3. any required path absent, or in `missing`, `not-supported` or
   `permission-denied` state, **and the outcome depends on it** → `unknown`;
4. otherwise → `pass` or `fail`.

Step 3 carries the clause that section 8 exists for. The order is fixed here
rather than left to the engine, because an engine free to choose its own order
could turn an invalid value into a pass by evaluating applicability first.

---

## 13. What a collector must never decide

- whether a resource is compliant;
- how severe anything is;
- what should be done about it;
- whether a missing fact "probably" means the default;
- that an error is an empty result;
- that a throttled or truncated response is a complete one.

The last two are how this model fails in practice. Neither looks like a
decision when it is written: one is a `catch` that returns `[]`, the other is
a loop that stops at the first page. Both produce evidence that is confident
and wrong, and no rule downstream can detect either.

Any collector that cannot complete a fact says so, with a state and a reason,
and hands the problem to a place where a human can see it.
