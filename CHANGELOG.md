# Changelog

Versions follow [semantic versioning](https://semver.org). Below `1.0.0` the
interfaces may change; when they do, it is said here.

Rules carry their own versions, independently of this file. See
[docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md).

---

## 0.1.0-alpha

First public release. Alpha because the rule set is two rules, not because the
engine is unfinished.

**Breaking changes:** none. There is nothing to break yet.

### What works

- a declarative rule format where every rule states what kind of claim it
  makes, and cannot be merged without saying how it can pass while the problem
  survives;
- six outcomes, with `unknown` never aggregated as a pass;
- bounded evaluation: incomplete evidence still decides when the bound settles
  the question, and returns `unknown` only when the missing part could change
  the answer;
- validation in six layers ordered by scope, each constraint owned by exactly
  one of them;
- a read-only SharePoint collector in PowerShell, with provenance, collection
  states and declared coverage;
- reports in Markdown and JSON, both carrying the evidence a finding came from
  and what it does not establish;
- 100 tests, all offline, including a sabotage per invariant.

### Rules

| id | basis | What it checks |
|---|---|---|
| `SPO-LIST-001` v2.0 | `documented-limit` | A list past 100,000 items that still inherits permissions |
| `SPO-SITE-001` v1.0 | `convention` | A site with fewer than two owners |

### Known limitations

- **Two rules.** This is a model with a working engine, not coverage.
- **Delegated identity only.** Both authentication modes see what one person
  sees, and every report says so. A tenant-wide inventory needs an application
  identity with `Sites.Read.All` and admin consent, which is not implemented.
- **No group expansion.** A group owner counts as one principal and the
  collector declares the expansion `not-attempted`, emitting a lower bound
  rather than a count it cannot prove.
- **One profile.** A second is created when a concrete rule needs to differ.
- **No source liveness checking.** Whether a source still says what a rule
  claims can only be checked by a person, and always will be.
- **SharePoint only.** Exchange, Teams and Entra collectors do not exist.

### Validated against

PnP.PowerShell 3.3.0, and one Microsoft 365 tenant, read-only, on 2026-08-06.
Both collector paths ran, produced evidence that validates against the schema,
and returned findings through the engine.

Two defects were found by that run and fixed. Neither was visible offline:
`Connect-PnPOnline` requires a client id since PnP 2.99, and a CSOM property
read through the context returns null without raising.
