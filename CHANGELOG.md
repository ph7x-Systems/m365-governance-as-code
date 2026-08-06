# Changelog

Versions follow [semantic versioning](https://semver.org). Below `1.0.0` the
interfaces may change; when they do, it is said here.

Rules carry their own versions, independently of this file. See
[docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md).

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
