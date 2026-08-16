![Microsoft 365 Governance as Code, by pH7x Systems](https://raw.githubusercontent.com/ph7x-Systems/m365-governance-as-code/main/docs/banner.png)

# Microsoft 365 Governance as Code

[![PyPI](https://img.shields.io/pypi/v/m365-governance-as-code?label=PyPI&color=0073b7)](https://pypi.org/project/m365-governance-as-code/)
[![Python](https://img.shields.io/pypi/pyversions/m365-governance-as-code?color=3776ab)](https://pypi.org/project/m365-governance-as-code/)
[![Licence](https://img.shields.io/pypi/l/m365-governance-as-code?color=2ea44f)](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/ph7x-Systems/m365-governance-as-code/ci.yml?branch=main&label=CI)](https://github.com/ph7x-Systems/m365-governance-as-code/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-ph7x.com-1f6feb)](https://ph7x.com/tools/m365-governance-as-code/docs/)

> Each badge reports something measured. The Python versions are the ones CI
> runs the suite against, and the CI badge is the state of `main`. None of them
> is a claim about the governance conclusions this engine produces; those
> declare their own basis, one rule at a time.


> **Every governance conclusion must declare what kind of truth it is.**
>
> **Automation may verify a claim. It may never strengthen it.**

Governance checks that show their work. PowerShell collects facts. Python
evaluates declarative rules. Every finding says what kind of claim it is,
which evidence it came from, and what it does not establish.

Nothing here changes anything in a tenant. There is no write path, no
remediation command, and no `--fix-all`.

**Scope.** This project evaluates the Microsoft 365 tenant that exists today.
It does not infer the characteristics of an estate it has not observed. There
are two modes, and the engine never knows which one produced the evidence it
is reading: **Live** observes Microsoft 365 directly, **Assessment** evaluates
evidence exported by something else and says so on the first line of every
report. See [docs/SCOPE.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/SCOPE.md).

**Why it exists.** We kept writing the same governance findings into
documents, and kept watching them lose the one thing that made them useful:
whether the finding was a rule Microsoft enforces, a limit it imposes, advice
it gives, or our own opinion. This project is that distinction, made
executable and made impossible to skip.

**Status:** `1.0.0-beta.1`. 18 rules, a ten-mode collector validated
against a live tenant, 8 profiles, ten commands and 350 tests at 91 per
cent coverage. Beta because the model has stopped moving: the outcomes, the
resolution order, the basis types and the evidence schema are frozen, and
[docs/MILESTONE-A.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/MILESTONE-A.md) records what closing SharePoint
end to end actually cost. The rule set is still small, and that is the next
milestone rather than a caveat on this one.

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

Full model in [docs/TRUST-MODEL.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/TRUST-MODEL.md).

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

Details in [docs/ARCHITECTURE.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/ARCHITECTURE.md) and
[docs/JSON-SCHEMA-PLAN.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/JSON-SCHEMA-PLAN.md).

---

## Install

```bash
pip install m365-governance-as-code==1.0.0b2
```

The `==` is not optional yet. `1.0.0b1` is a pre-release under PEP 440, and pip
skips pre-releases unless a version is pinned or `--pre` is given, so plain
`pip install m365-governance-as-code` resolves to nothing until there is a
stable release.

The rules, profiles, schemas and the collector ship inside the package, so an
installed copy works from any directory. Nothing resolves against a checkout.

Requires Python 3.11 or later. The collector additionally requires
PowerShell 7 and PnP.PowerShell, and is not needed to run anything below.

To work on the project instead of using it:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . && pip install -r requirements-dev.txt
```

### Your own rules

The packaged set is what runs when you supply nothing. A path replaces it
entirely:

```bash
m365-governance evaluate --rules ./my-rules --evidence ./evidence
```

**It replaces; it never merges.** Either the set that shipped with this
version, complete, or the set you supplied, complete. A rule set assembled
from both would exist only in the memory of whoever typed the command, and two
runs of the same version would stop meaning the same thing. Every report says
which of the two it used.

---

## Quick start

Five commands. All of them run offline, against fixtures. No tenant required.

```bash
pip install m365-governance-as-code==1.0.0b2   # 1. install
m365-governance doctor                # 2. is anything broken here
m365-governance list-rules            # 3. what ships with this version
m365-governance show-rule SPO-LIST-001
m365-governance evaluate --evidence <an-evidence-file.json>
```

Example evidence ships with the package. `doctor` confirms it is there, in the
`packaged content` line, but does not print the path. This does:

```bash
python -c "import m365_governance, pathlib; print(pathlib.Path(m365_governance.__file__).parent / 'data' / 'fixtures')"
```

`explain unknown` is the one to run second. The project rests on six words
being different from each other, and the difference between "we could not read
this" and "this is fine" is the whole of it.

`show-rule` is the one to run first. It prints the whole claim: the basis, the
rationale behind the severity, the evidence the rule cannot decide without,
the source, and how the rule can pass while the problem survives.

---

## The commands

| | |
|---|---|
| `explain OUTCOME` | What `pass`, `fail`, `unknown`, `not-applicable`, `invalid-evidence` and `error` mean, and what each is not. `explain all` for the six |
| `collect SLICE` | Run a collector against a tenant and write evidence. Evaluates nothing |
| `doctor` | Python, dependencies, schemas, rules, profiles, and whether PowerShell is around. Says what it found, not only whether it liked it |
| `list-rules` | Every rule with the kind of claim it makes, strongest claim first |
| `show-rule ID` | One rule in full, including what it does not establish |
| `stats EVIDENCE` | What a collector managed to see, before anything is evaluated |
| `validate` | Every rule against the schemas and the invariants |
| `evaluate` | Rules against evidence: one document or a directory of them. Markdown, JSON or self-contained HTML |
| `report RUN.json` | Re-render a stored run in another format, without evaluating again |
| `diff BEFORE AFTER` | What moved between two assessments, and what that does not establish |

`diff` is the one a periodic audit needs:

```
## SPO-SITE-001

**pass → fail**

Evidence that moved:

| Path | Before | After |
|---|---|---|
| `owners.count` | 2 | 1 |
```

It reports the rule version alongside the outcome, because a result that moved
because somebody edited the rule is not a result that moved because somebody
removed an owner. `--fail-on-regression` exits non-zero when any rule left
`pass`, including for `unknown`: losing the answer is a regression too.

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
That table lives in [docs/ARCHITECTURE.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/ARCHITECTURE.md), not in each
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

One example per outcome is in [examples/](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/examples/), every one of them
produced by a real run and checked by CI. There is no example of `error`: a
rule cannot author one, so an example of it would be an example of a bug.

---

## Limitations

Stated here rather than discovered:

- **Two rules.** This is a model with a working engine, not a coverage tool.
- **The collector runs delegated, never as an application.** It has been run
  read-only against a real tenant and validated against PnP.PowerShell 3.3.0,
  but a delegated run sees what one person sees. Every report says so on its
  first line. A tenant-wide inventory needs an application identity with
  `Sites.Read.All` and admin consent, and that is not implemented.
- **No group expansion.** The collector emits `minimum_count` and declares
  the expansion `not-attempted`. That is honest and the engine handles it; it
  is not the same as counting.
- **One profile.** A second one is created when a concrete rule needs to
  differ, not before.
- **Source liveness is not checked**, and whether a source still supports the
  claim can only be checked by a person.
- **The model has not been reviewed by anyone outside its authors.** Two
  independent reviews are pending; see
  [docs/review/RULE-REVIEW.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/review/RULE-REVIEW.md). Changes already
  decided but deliberately not yet applied are in
  [docs/POST-REVIEW-CHANGES.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/POST-REVIEW-CHANGES.md).

---

## Permissions

The collector is read-only and asks for the least that works:

Verified by running it, delegated, against a live tenant on 2026-08-06:

| Fact | Cmdlet | Identity used |
|---|---|---|
| Site owners | `Get-PnPSiteCollectionAdmin` | site collection administrator |
| List item count | `Get-PnPList` | read on the site |
| Permission inheritance | `Get-PnPList -Includes HasUniqueRoleAssignments` | read on the site |

`-ClientId` is required by this collector. PnP.PowerShell removed its own
multi-tenant application in [2.12.0](https://github.com/pnp/powershell/blob/dev/CHANGELOG.md),
so a connection with no client id anywhere fails before it reaches the network.
Register an Entra ID app, or use one your tenant already has.

The module accepts a
[default client id](https://pnp.github.io/powershell/articles/defaultclientid.html)
instead — `Set-PnPManagedAppId`, or `ENTRAID_APP_ID` / `ENTRAID_CLIENT_ID` /
`AZURE_CLIENT_ID`. This collector still asks for it explicitly, because
evidence has to say which identity observed it and an ambient environment
variable is one nobody can name afterwards.

An interactive sign-in produces `identity_kind: delegated`, and every report
built from it says so: that run saw what one person sees, and nothing in it
may be read as a tenant-wide statement.

A fact the identity may not read comes back as `permission-denied`, never as
absent and never as compliant.

---

## Roadmap

`1.0.0-beta.1` is the baseline. Milestone A closed SharePoint end to end and
does not reopen; see [docs/MILESTONE-A.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/MILESTONE-A.md).

**Epic B is open**: everything one identity cannot see. Application
authentication, group expansion, importers, HTML reporting, and SARIF once the
representation of `unknown` is decided. The model is frozen for the whole of
it. See [docs/EPIC-B.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/EPIC-B.md).

The table below is the direction, ordered by what would make the tool useful
to somebody else soonest rather than by what is most interesting to build.

| | |
|---|---|
| **More SharePoint rules** | Retention, site lifecycle, and the classification rules a tenant that uses labels would need. The engine is done; the work is authoring claims honestly. |
| **Coverage across a run** | Six of 53 sites refused the collector, and a report over the other 47 says 47 without saying "of 53". The envelope records coverage per document; nothing records it per run. |
| **Group expansion** | A group owner is one principal and may be forty people. The collector declares the expansion `not-attempted` and emits a lower bound; expanding it turns bounds into counts. |
| **Application authentication** | Delegated runs see what one person sees, and every count in this repository carries that clause. A tenant-wide inventory needs an app identity with `Sites.Read.All` and admin consent. |
| **Exchange, Teams and Entra collectors** | The evidence schema is service-agnostic. Each collector is new code and no new model. |
| **HTML reporting** | Markdown and JSON exist. HTML is for the reader who is not in a terminal. |
| **SARIF output** | So findings appear where code findings already appear, in a pipeline's own UI. Blocked until `unknown` has an agreed representation: SARIF has six `kind` values and this project has six outcomes, and they are not the same six. |

Open issues are the current list. This table is the direction.

**Not on the roadmap, ever:** automatic remediation, rules that execute code,
inferring `basis` from a source, or treating missing evidence as compliance.

---

## Contributing

Rules are the interesting contribution. A pull request that adds one is
reviewed against [docs/review/RULE-REVIEW.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/review/RULE-REVIEW.md),
and the criterion is not agreement — it is disagreeing in the right place.

Read [CONTRIBUTING.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/CONTRIBUTING.md) first; it is short. Before opening a
pull request:

```bash
m365-governance validate
pytest
python tools/examples.py --check
```

Also: [CODE_OF_CONDUCT.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/CODE_OF_CONDUCT.md) ·
[SECURITY.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/SECURITY.md) · [CHANGELOG.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/CHANGELOG.md)

The build fails, deliberately, when a rule is missing `basis`, when a
documented type has no source, when a convention has no rationale, when
`passes_without_resolving` is missing, when a condition reads evidence nobody
declared, when evidence is declared and never consumed, when a failure message
interpolates a value that is missing precisely when that message prints, when
a YAML key is duplicated, when two rules share an id, or when any unknown
field appears anywhere.

That last one is `additionalProperties: false` everywhere, and it is not
pedantry: `severty: high` must stop the build, not disappear.

When you change a rule, read [docs/CHANGE-POLICY.md](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/docs/CHANGE-POLICY.md).
The test is one sentence: *if a report produced yesterday would be interpreted
differently today, the rule version must change.*

---

## License

MIT. See [LICENSE](https://github.com/ph7x-Systems/m365-governance-as-code/blob/main/LICENSE).
