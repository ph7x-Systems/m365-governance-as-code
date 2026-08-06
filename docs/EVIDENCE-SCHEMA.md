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

### `imported`, the third kind

Evidence does not always come from a collector we wrote. A migration tool
exports an inventory, somebody sends a CSV, and the facts in it are perfectly
usable. What is not usable is the assumption that we know how they were
gathered.

```yaml
provenance:
  collected_at: 2026-06-30T09:00:00Z
  collector: sharegate-import-adapter
  collector_version: 0.1.0
  source_system: ShareGate
  identity_kind: imported
  import_source:
    tool: ShareGate Desktop
    version: "24.1"
    exported_at: 2026-07-14T16:41:00Z
    exported_by: migration-team@contoso.com
```

An import carries **no `scopes`**, and the schema forbids them. Writing
`scopes: []` would read as "no permissions were needed" rather than "this does
not apply", and those are opposite claims. For the same reason a live run may
not carry an `import_source`: the two are exclusive, and a document that
carried both would be lying about one of them.

Every report built from imported evidence says so:

> This assessment is based on imported evidence. Collection completeness
> cannot be verified by this engine.

That is a fact with consequences rather than a disclaimer. We did not choose
the scope of that export, we do not know what the exporting identity could
read, and we cannot reproduce it. An `unknown` from a live run means "collect
it again". An `unknown` from an imported run may mean "ask whoever ran the
export".

**`collected_at` and `exported_at` are deliberately separate.** The first is
when the facts were observed; the second is when the file was written. They
are usually the same moment. When they are not, the evidence is older than the
document that carries it, and the report says how much older: an export
produced today from a scan that ran six weeks ago describes a tenant that no
longer exists, and the reader is the last person able to notice.

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

---

## 14. What kind of list this is

A collector records what the product says about a list, and stops there:

```yaml
facts:
  list:
    is_catalog:     { state: observed, value: true,  raw: { field: IsCatalog, value: true } }
    is_system:      { state: observed, value: false, raw: { field: IsSystemList, value: false } }
    is_application: { state: observed, value: false, raw: { field: IsApplicationList, value: false } }
    hidden:         { state: observed, value: false, raw: { field: Hidden, value: false } }
    base_template:  { state: observed, value: 121,   raw: { field: BaseTemplate, value: 121 } }
```

Every one of those is SharePoint's own answer, verified against the CSOM type.
**The collector does not classify**, and it does not filter: a collector that
dropped system lists would be deciding what matters, and a library holding
60,000 unique permission scopes matters whoever created it.

The classification is a derivation, and it is exactly one thing: an order of
precedence over those facts. `is_catalog` first, because a catalog is a store
the platform reads from and nobody puts a document in one on purpose. Then
`is_application`, then `is_system`.

**That order was corrected against a real tenant.** Written from the
documentation, `is_system` came second, and 23 real lists showed why that was
wrong: `Site Pages` and `Site Assets` come back with `is_system` and
`is_application` both true. They were provisioned by the platform and they
hold the pages of the site. Reading `is_system` first labelled them plumbing
and moved a site's own pages down the report.

**What these flags cannot do.** They answer "who provisioned this", not "is
this worth reading". Usually the two coincide. `App Packages`, the site
collection app catalog, comes back as none of the three and is therefore
`content`, which is wrong in every sense except the one that matters: it is
what the product says. The alternative is matching on a title, and matching on
a title is how a classifier starts lying in a language it was never tested in.

**Absence of all three is `unknown`, never `content`.** A list nobody
classified is a list nobody looked at.

### What a profile may do with the label

Move it down the page. Nothing else.

```yaml
set_aside_classes:
  - system
```

A set-aside resource is still collected, still evaluated, still counted in the
summary, and still printed, under its own heading at the end. The key is not
called `exclude` because excluding is the dangerous version: a document
library over a hard product limit is over it whoever created it, and
SharePoint calling it a catalog is not a reason for a governance report to
stay silent about it.
