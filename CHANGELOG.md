# Changelog

Versions follow [semantic versioning](https://semver.org). Below `1.0.0` the
interfaces may change; when they do, it is said here.

Rules carry their own versions, independently of this file. See
[docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md).

---

## 0.4.1-alpha

A support link, and a boundary around it.

**Breaking changes:** none.

The link lives in three places somebody would go looking for one: a badge at
the top of the README, a Support section at the bottom, and the Sponsor button
GitHub renders from `.github/FUNDING.yml`.

It appears nowhere else, and a test enforces that. Nothing in the CLI output,
nothing in a Markdown or HTML report, nothing in a rule. A person running a
governance check is reading a finding, and that is not the moment to ask them
for anything. The HTML report is the one that matters most here: it is the
format most likely to be forwarded to somebody who never ran the tool.

---

## 0.4.0-alpha

Collector modes, and the first rules written against facts the collector did
not previously gather.

**Breaking changes:** the collector's `-Mode` parameter is mandatory. A script
calling it without one now fails instead of guessing.

### Collector

Five modes, each writing one evidence document per resource:

| Mode | Reads |
|---|---|
| `SiteOwners` | the owners of one site |
| `SiteSharing` | sharing capability, default link type and permission, anonymous link expiry |
| `List` | one list: item count and permission inheritance |
| `UniquePermissions` | every visible list on a site |
| `TenantSites` | every site the identity can enumerate |

`TenantSites` writes the enumeration caveat into every document it produces. A
delegated run does not enumerate a tenant, it enumerates what one person can
see, and the number it could not see is not knowable from inside the run.

Counting unique permission scopes is behind `-CountUniqueScopes` because it
walks every item of every list. Without it the count is reported as
`not-supported`, which is the truth about that run. A zero would have been an
invention, and every rule that needs the number returns `unknown` instead.

### Rules

| id | basis | Threshold |
|---|---|---|
| `SPO-LIST-002` | `documented-limit` | 50,000 unique permission scopes |
| `SPO-LIST-003` | `documented-guidance` | 5,000, the recommended figure |

Both read the same number and are deliberately separate. One is a ceiling the
product enforces, the other a recommendation it permits exceeding, and
collapsing them would put a performance note and a hard limit under the same
heading.

A sharing rule was **not** written. The facts are collected; classifying them
needs the enum values confirmed against a tenant that has them, and guessing
at `AnonymousAccess` versus `Anyone` would be inventing a fact to put in a
`basis`.

### A partial count is a lower bound

Evidence is monotonic: a collector that stopped at 20,000 items saw at least
what it counted. A scalar fact in `partial` state now resolves to a bound
rather than to an absence, so a list counted in part to 6,100 scopes **fails**
the 5,000 recommendation and returns **unknown** against the 50,000 ceiling.
One is proven by the bound, the other is not.

### Fixed

Three `unknown` messages claimed the evidence had not been collected. With a
partial count, or an unexpanded group, it had been: the message said "were not
collected" while the evidence line beside it read "at least 6,100". They now
say that the count does not settle the question and point at the evidence for
which case it is. `SPO-SITE-001` moves to v1.1 for it.

The `default` profile enumerated its rules, and the enumeration went stale the
first time a rule was added: two new rules were written, validated, tested,
and silently filtered out of every evaluation. A profile that means everything
now says so by not choosing.

187 tests.

---

## 0.3.0-alpha

Scope, written down, and the first change to the evidence model since it was
settled.

**Breaking changes:** none for existing documents. Every evidence file that
validated against `1.0.0` still validates.

### Scope

[docs/SCOPE.md](docs/SCOPE.md) states what this project will not do:

> This project evaluates the Microsoft 365 tenant that exists today. It does
> not infer the characteristics of an estate it has not observed.

Two modes, and **the engine never knows which one produced the evidence**.
**Live** observes Microsoft 365 directly. **Assessment** evaluates evidence
exported by something else.

The separation exists because the alternative is a tool that answers every
question and answers some of them from nothing. A destination recommendation
made against a tenant with no source inventory would have to infer the source;
it would produce an answer, the answer would be plausible, and nobody reading
it could tell which parts were observed. That is the failure this project is
built against, in its most tempting form: not a wrong answer, a confident one.

### `identity_kind: imported`

Evidence schema `1.1.0`. A third kind of provenance, for facts that were
gathered by something else:

```yaml
identity_kind: imported
import_source:
  tool: ShareGate Desktop
  version: "24.1"
  exported_at: 2026-07-14T16:41:00Z
  exported_by: migration-team@contoso.com
```

An import carries **no `scopes`**, and the schema forbids them: `scopes: []`
reads as "no permissions were needed" rather than "this does not apply", and
those are opposite claims. A live run may not carry an `import_source` for the
same reason. The two are exclusive.

Every report built from imported evidence says so, as prominently as the
delegated warning and before the first finding:

> This assessment is based on imported evidence. Collection completeness
> cannot be verified by this engine.

**`collected_at` and `import_source.exported_at` are separate on purpose.**
The first is when the facts were observed, the second when the file was
written. When they differ the report says by how much: an export produced
today from a scan that ran six weeks ago describes a tenant that no longer
exists, and the reader is the last person able to notice.

### Not done, and deliberately

No score, no rating, no stars. A summary that reads `★★★★☆` is read as "this
is fine", and the reader stops there. Every line of a summary keeps the nature
of its truth, or there is no summary.

166 tests.

---

## 0.2.1-alpha

`explain`, which was the largest gap in using the tool.

**Breaking changes:** none.

```bash
m365-governance explain unknown
m365-governance explain all
```

Each outcome states what it means, what it is not, how it aggregates, what a
pipeline does with it, and shows a line from a real report.

The "what it is not" section carries the weight. Every outcome here has a
wrong reading that is more comfortable than the right one, and `unknown` has
the most comfortable of all: that nothing was found, so nothing is wrong.

Three of the entries say something the README did not:

- an `unknown` is not the same as incomplete evidence. Incomplete evidence
  often still decides, and `unknown` is returned only when the missing part
  could change the answer;
- `invalid-evidence` differs from `unknown` by the fix. One is fixed by
  collecting again, the other by repairing the collector;
- moving from `pass` to `not-applicable` is flagged as a regression, and that
  is deliberate. It is often legitimate, and it always means an answer you had
  yesterday is gone today.

One test evaluates a fixture and compares the exit code with what `explain`
claims about it, so the text cannot drift from the behaviour it describes.

152 tests.

---

## 0.2.0-alpha

Commands, so the project can be used and not only validated. No change to the
trust model, the rules, the schemas or the engine's semantics.

**Breaking changes:** none.

### New commands

| | |
|---|---|
| `doctor` | Python, dependencies, schemas, rules, profiles, PowerShell. Reports what it found, not only whether it liked it, so a bug report carries versions |
| `list-rules` | Every rule with its basis and severity, strongest claim first |
| `show-rule ID` | One rule in full: basis, rationale, evidence, condition, all five messages, sources, and how it can pass while the problem survives |
| `stats EVIDENCE` | What a collector managed to see, before anything is evaluated. Shows a bound as a bound |
| `report RUN.json` | Re-render a stored run without evaluating it again |
| `diff BEFORE AFTER` | What moved between two runs |

`evaluate` and `report` gained `--format html`: one self-contained page, no
external requests, and no colour doing work that a word is not also doing.

### On `diff`

It reports the rule version alongside the outcome. A result that moved because
somebody edited the rule is not a result that moved because somebody removed an
owner, and a comparison that cannot tell them apart is worse than none.

`--fail-on-regression` exits non-zero when a rule leaves `pass`, and that
includes leaving it for `unknown`. Losing the answer is a regression.

It accepts a stored report or an evidence document on either side, because an
audit usually has one of each: last quarter archived, this morning collected.

### Also

- `Run.from_dict` and `Result.from_dict`, with a test that the round trip is
  lossless. A field dropped there would disappear the second time somebody
  opened the report;
- a test that the reading commands never print a verdict, and that neither
  `inspect` nor `doctor` imports the engine. A reading command that could
  evaluate is one refactor away from doing it;
- 138 tests.

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
