# Microsoft 365 Governance as Code

> **Every governance conclusion must declare what kind of truth it is.**
>
> **Automation may verify a claim. It may never strengthen it.**

Governance checks that show their work. PowerShell collects facts. Python
evaluates declarative rules. Every finding says what kind of claim it is,
which evidence it came from, and what it does not establish.

Nothing here changes anything in a tenant. There is no write path, no
remediation command, and no `--fix-all`.

---

## The problem

Most governance tooling produces a green box. A green box has no grammar for
the difference between these four sentences:

- the product **enforces** this;
- the product **imposes** this boundary, and here is the number;
- Microsoft **recommends** this, and permits the alternative;
- **we think** this is a good idea.

Those four produce different conversations, different budgets and different
arguments with an auditor. A tool that renders them identically has removed
the only information the reader needed.

And a green box has no grammar for the most common outcome of all: *we could
not read this*. Missing evidence is a fact about collection, not a fact about
the resource, and the moment it renders as a pass the whole report becomes
unreliable in a way nobody can see.

---

## The trust model

Every rule declares a `basis`. There are five, and the distinction between
them is the point of the project:

| basis | Meaning | Requires |
|---|---|---|
| `requirement` | The product enforces this | a source |
| `documented-limit` | A boundary the product imposes, with a number | a source, and the limit stated next to the observed value |
| `documented-guidance` | Microsoft recommends it; the alternative is permitted | a source |
| `convention` | Widely held practice, documented by nobody | a rationale |
| `opinion` | Our position, stated as ours | a rationale |

**A source never decides the type.** An opinion may cite documentation. A
convention may cite documentation. The source explains the claim; it does not
change what kind of claim it is.

**The engine never classifies.** `basis` is authored by a person and carried
into the report unchanged. The schema verifies that it is present and
justified; it never infers what it should be. That boundary is the whole
difference between automation that verifies and automation that strengthens.

Six outcomes, and `unknown` is never a pass:

```
pass · fail · unknown · not-applicable · invalid-evidence · error
```

`error` is the only one a rule may not author a message for: it describes the
engine, not the resource.

Full model in [docs/TRUST-MODEL.md](docs/TRUST-MODEL.md).

---

## Architecture

```
collectors  ─→  evidence  ─→  engine  ─→  results  ─→  reports
                   ▲            ▲
                schemas      rules + profile
```

Evidence flows one way. Nothing downstream writes back.

Validation happens in six layers, ordered by **scope**, and every constraint
has exactly one owner — a constraint enforced in two places will diverge the
first time one of them is corrected:

| Layer | Scope | Example |
|---|---|---|
| 1 | the file is a document | duplicate YAML keys |
| 2 | one field | `basis` is one of five |
| 3 | one file, references followed | `required` equals what the rule consumes |
| 4 | every file | duplicate ids |
| 5 | the outside world | the source URL resolves |
| 6 | a person | the source still says what the rule claims |

Layer 6 is numbered like the others on purpose. No validator can prove that a
rule represents a document correctly, and pretending otherwise would be the
exact failure the trust model exists to prevent.

Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/JSON-SCHEMA-PLAN.md](docs/JSON-SCHEMA-PLAN.md).

---

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
```

Requires Python 3.11 or later. The collector additionally requires
PowerShell 7 and PnP.PowerShell, and is not needed to run anything below.

---

## Quick start

Everything runs offline against fixtures. No tenant is required.

```bash
# every rule, every layer
m365-governance validate

# one evidence document, human readable
m365-governance evaluate \
  --rules rules/sharepoint \
  --evidence fixtures/sharepoint/list-over-limit.json \
  --format markdown

# the same, as JSON
m365-governance evaluate \
  --rules rules/sharepoint \
  --evidence fixtures/sharepoint/site-partial-expansion-decides.json \
  --format json
```

`--fail-on unresolved` exits non-zero on `fail`, `unknown`, `invalid-evidence`
and `error`, which is the setting to use in a pipeline: it refuses to treat
"we could not read this" as success.

---

## A rule

```yaml
schema_version: "1.0"
id: SPO-SITE-001
version: "1.0"
title: A site should have at least two owners

basis:
  type: convention
  sources: []
  rationale: >
    Microsoft does not require a minimum number of owners, does not warn about
    a single owner, and does not prevent a site from having one. This is our
    recommendation, and an organisation may reasonably decline it.

severity:
  default: medium
  rationale: >
    The consequence is delay, not exposure. Access decisions queue behind a
    person who is not there.
  configurable: true

evidence_requirements:
  - path: owners.count
    type: integer
    required: true

condition:
  operator: less-than
  evidence: owners.count
  value: 2

limitations:
  passes_without_resolving: >
    Two owners who are dormant, who have left, or who do not know they own the
    site satisfy this rule completely. The count is two and nobody is able to
    act.
```

`passes_without_resolving` is mandatory. It answers one question — *how can
this rule pass while the problem survives?* — and it is a field of its own
rather than one entry in a list because it is the one that gets omitted. An
author who cannot answer it has not yet understood what the rule measures.

Rules execute no code. The condition grammar has twelve operators and no
escape hatch, because a rule that can execute stops being reviewable by
anyone who does not read the language it executes in.

---

## Evidence

```json
{
  "facts": {
    "owners": {
      "state": "observed",
      "direct": [{"principal_id": "user-1", "principal_type": "user"}],
      "groups": [{"principal_id": "group-1", "principal_type": "group",
                  "expansion": {"status": "not-attempted"}}],
      "expansion_complete": false,
      "minimum_count": 1
    }
  }
}
```

A group owner is one principal and may be forty people. When expansion is
incomplete the collector emits a **bound**, never a guess, and the engine
reasons from the bound:

- three direct owners and one unexpanded group proves `at least 3`, so
  `owners >= 2` is a **pass**, with certainty;
- one direct owner and one unexpanded group proves nothing about `owners < 2`,
  so the answer is **unknown**.

Without an upper bound the engine can prove `pass` and can never prove `fail`.
That table lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), not in each
rule: a rule author declares the condition, and the engine decides what can be
concluded from what was collected.

`[]` means observed, and there are none. A fact that was not collected is
never an empty list.

---

## Output

```markdown
### SPO-LIST-001 v2.0

The list holds 148000 items, above Microsoft's documented limit of 100,000,
and still inherits its permissions. Inheritance can no longer be broken on
this list, so it cannot be given unique permissions later.

- Basis: **documented-limit** — a boundary the product imposes
- Severity: medium
- Evidence: `items.count` = 148000, `permissions.inheritance_broken` = false
- Source: SharePoint limits, Items in lists and libraries — checked 2026-08-05
```

And when the answer is that there is no answer:

```markdown
1 rule could not be decided. That is not compliance: missing evidence is a
fact about collection, not about the resource.
```

More in [examples/](examples/), all generated by the commands above.

---

## Limitations

Stated here rather than discovered:

- **Two rules.** This is a model with a working engine, not a coverage tool.
- **The collector has not been run against a tenant.** Its interface, states
  and provenance are complete and it is proved read-only in CI, but the
  cmdlet surface is unverified against live SharePoint. Everything else runs
  offline against fixtures and does not depend on it.
- **No group expansion.** The collector emits `minimum_count` and declares
  the expansion `not-attempted`. That is honest and the engine handles it; it
  is not the same as counting.
- **One profile.** A second one is created when a concrete rule needs to
  differ, not before.
- **Source liveness is not checked**, and whether a source still supports the
  claim can only be checked by a person.
- **The model has not been reviewed by anyone outside its authors.** Two
  independent reviews are pending; see
  [docs/review/RULE-REVIEW.md](docs/review/RULE-REVIEW.md). Changes already
  decided but deliberately not yet applied are in
  [docs/POST-REVIEW-CHANGES.md](docs/POST-REVIEW-CHANGES.md).

---

## Permissions

The collector is read-only and asks for the least that works:

| Fact | Needs |
|---|---|
| Site owners | `Get-PnPSiteCollectionAdmin`, site collection admin or `Sites.FullControl.All` |
| List item count | `Get-PnPList`, read on the site |
| Permission inheritance | `Get-PnPList -Includes HasUniqueRoleAssignments`, read on the site |

An interactive sign-in produces `identity_kind: delegated`, and every report
built from it says so: that run saw what one person sees, and nothing in it
may be read as a tenant-wide statement.

A fact the identity may not read comes back as `permission-denied`, never as
absent and never as compliant.

---

## Contributing

Rules are the interesting contribution. A pull request that adds one is
reviewed against [docs/review/RULE-REVIEW.md](docs/review/RULE-REVIEW.md),
and the criterion is not agreement — it is disagreeing in the right place.

Before opening one:

```bash
m365-governance validate
pytest
```

The build fails, deliberately, when a rule is missing `basis`, when a
documented type has no source, when a convention has no rationale, when
`passes_without_resolving` is missing, when a condition reads evidence nobody
declared, when evidence is declared and never consumed, when a failure message
interpolates a value that is missing precisely when that message prints, when
a YAML key is duplicated, when two rules share an id, or when any unknown
field appears anywhere.

That last one is `additionalProperties: false` everywhere, and it is not
pedantry: `severty: high` must stop the build, not disappear.

When you change a rule, read [docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md).
The test is one sentence: *if a report produced yesterday would be interpreted
differently today, the rule version must change.*

---

## License

MIT. See [LICENSE](LICENSE).
