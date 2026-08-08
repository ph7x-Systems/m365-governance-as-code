# Product strategy

**Written 2026-08-07, against `1.0.0-beta.1` plus the unreleased commits on
`main`.**

> **The roadmap is driven by product capabilities, not by new commands or new
> rules. A release is complete when a capability is complete end to end.**

That sentence is the decision this beta produced. Early on, versions tracked
features: a command, a rule, a collector mode. From here they track closed
capabilities, and a capability is closed only when somebody can run it from
one end to the other without being told which part is missing.

**No new rule is written until the Must list in §6 is closed.** The product
does not need more claims. It needs the ones it has to survive being used.

> **A clean installation is the reference environment. The development
> repository is a convenience, not the execution model.**

The second principle, and it arrived by accident. Every test in this project
runs from the repository root, and so every test agreed that the product
worked. Installing it into an empty virtual environment took one command and
disagreed immediately.

A tool that only works when it is run from the root of a git checkout is not a
product yet. It is a development project that happens to have a command name.
**Nothing verified only from inside the repository counts as verified.**

---

Every claim below was checked by running the product, not by reading it. Where
running it contradicted the documentation, what it did is what is recorded.
Nothing here proposes code; the last section says what is still undecided.

---

## 1. Product statement

> **Microsoft 365 Governance as Code reads a tenant, applies rules that are
> published as text, and returns findings that each declare what kind of claim
> they are and what they could not establish.**

The sentence offered as a starting point said the tool "collects observable
evidence, evaluates explicit governance rules, and produces reproducible
findings that declare whether they are requirements, documented guidance,
limits or conventions."

**Two words in it are not yet supported by the product, and the sentence was
corrected rather than the product.**

- **"requirements"** — `list-rules` reports 2 `documented-limit`, 4
  `documented-guidance`, 10 `convention`. **Zero `requirement`. Zero
  `opinion`.** A product statement that names requirements describes a
  category with no members, so the sentence does not name them.

  **The type stays.** An empty category is not a wrong category: it says the
  rule set does not yet cover a claim of that kind, which is exactly what the
  model exists to make visible. If a documented Microsoft obligation is found
  tomorrow, nothing about the model has to change to hold it. What changes is
  how this is described in public. Never "supports all five types"; instead:

  > The rule model defines five truth categories. The current rule set
  > exercises three of them.

- **"reproducible"** — a single-resource run can be stored and re-rendered. A
  tenant-scale run cannot: see §3, Reporting and Diff. **Reproducibility is
  the promise of this project and it is not yet fully met**, which is why
  closing that loop is the first thing in §6.

**A correction, recorded rather than quietly dropped.** An earlier draft of
this document stated that the public page at ph7x.com over-claimed by naming
all five types. It does not. The page presents the five as a table of what the
model defines, and never says the rule set exercises them all. That draft was
written from a summary of the page rather than from the page, which is the
failure this project's own working rule exists to prevent.

---

## 2. Users

Three, and the third is the one the product is furthest from serving.

### The SharePoint or Microsoft 365 administrator

**Brings:** "Somebody asked whether our sites are governed and I do not know
what to answer."

**Runs first:** `doctor`, then `collect sites`, then `evaluate`.

**Needs:** a list of sites with something wrong, in an order, that they can
hand to somebody. Plus the confidence that a site missing from the list was
looked at.

**Missing today:** the run they will actually produce — one evidence file per
site in a directory — evaluates fine and then cannot be stored and reopened.
`report` refuses it and `diff` refuses it. They also get a wall of `unknown`
unless they pair the slice with the right profile, and the command that tells
them which profile to use is a hint printed after collection, not a default.

### The architect or consultant

**Brings:** "I need to say something defensible about a tenant that is not
mine, to somebody who will push back."

**Runs first:** `show-rule`, before ever touching a tenant. This is the
persona the product currently serves best.

**Needs:** the basis, the source, the severity rationale, and the sentence
about how the rule can pass while the problem survives. All four exist and are
printed.

**Missing today:** an HTML report designed for somebody who did not write the
rules, and a way to compare a tenant to itself three months later.

### The governance or security team

**Brings:** "Is this getting better or worse, and can it run without a person?"

**Runs first:** `evaluate --fail-on` in a pipeline.

**Needs:** history, trend, and a machine-readable output that lands in the
tooling they already have.

**Missing today:** almost all of it. Gating works. Storing does not. SARIF is
blocked on an unresolved question about `unknown`. This persona is the reason
Epic B exists and the reason 1.0 is not close.

---

## 3. Current capabilities

Behaviour, not the existence of a class or a command. Everything marked
**Tenant-tested** was run against `joaolivio.sharepoint.com`, 53 sites, a
delegated identity.

| Capability | Exists | Tenant-tested | Complete enough for beta | Gap |
|---|---|---|---|---|
| **Ownership** | yes | yes | yes | Group owners are a lower bound, never a count. A site "with at least 1 owner" may have forty or one. |
| **Sharing** | yes | yes | yes | Reads what a site permits, never who used it. No rule on anonymous-link expiry: `0` is ambiguous in the product. |
| **Permissions** | yes | yes | yes | Unique-scope counting is opt-in and expensive; off, the count is `not-supported` and rules return `unknown`. |
| **Capacity** | yes | yes | yes | A site with no quota is reported as having no quota, which is correct and is not a number anybody can act on. |
| **Modernity** | yes | yes | yes | Reports how a site is built. Says nothing about whether anybody uses the classic parts. |
| **SPFx** | yes | yes | **no** | **Not reachable from the CLI.** `SpfxCatalog` and `SpfxPages` are collector modes with a rule and a profile, and there is no `collect spfx`. Only the PowerShell script can produce this evidence. |
| **Activity** | yes | yes | yes | Reads writes, never reads. A reference site nobody edits fails; that is the true answer to the question asked and not to the one a reader has. |
| **Classification** | yes | yes | yes | The validating tenant has no labels at all, so SPO-CLASS-002 has never fired outside a fixture and SPO-CLASS-001 fails on every site. |
| **Imported evidence** | **partly** | no | **no** | The schema accepts `identity_kind: imported` and the report renders the warning. **There is no importer.** No `import` command, no adapter, no format studied. Producing imported evidence means writing JSON by hand. |
| **Reporting** | yes | yes | **partly** | Markdown, JSON and self-contained HTML all render; the HTML made zero external requests across 57 resources. **`report` cannot re-render a many-resource run** — the exact shape `evaluate` produces over a directory. |
| **Diff over time** | yes | no | **no** | Works for one resource. **Fails for a directory**, which is the only shape a tenant produces. There is no snapshot store, so "over time" is currently "between two files somebody kept". |
| **CI/pipeline use** | yes | no | yes | `--fail-on fail` and `--fail-on unresolved` both exit non-zero, including over a directory. The default is `never`, so a pipeline that forgets the flag passes silently. |

### Defects found by running, during this inspection

Recorded, not fixed — this pass changes no code.

1. **`doctor` reports `profile default: 0 rules selected`, then says "Nothing
   is broken".** The default profile has no `rules` key, which means *every*
   rule. `cli.py` reads that correctly; `doctor.py` prints `len(selected)` on
   the raw value. A user reading `doctor` concludes the default profile
   evaluates nothing.
2. **`stats` prints `permission-denied9`** — a column width that does not fit
   the longest state name.
3. **Both schema `$id` URLs 404.** `https://ph7x.com/schemas/m365-governance/evidence/1.2.0`
   and `.../rule/1.0.0` are the published identities of the two schemas and
   neither resolves.
4. **The package does not contain the product.** This is the most serious
   finding of the inspection, and it only appears by installing.

   `pip install .` into a clean environment succeeds. The CLI runs and reports
   `1.0.0b1`. Then, from outside the repository:

   ```
   doctor      FAIL schemas / rules / profiles not found
   list-rules  document error: rules: not a directory
   ```

   `pyproject.toml` declares no package data. `rules/`, `profiles/`,
   `schemas/` and `collectors/` are not in the wheel; only the Python module
   is. Every path is resolved against the working directory, so an installed
   copy finds nothing. **Of ten commands, `explain` is the only one that works
   on an installed copy.**

   There is also no tag, no GitHub release, and `pypi.org` returns 404 — but
   publishing the package as it stands would ship a CLI that cannot find its
   own rules.

5. **The classifier still says alpha.** `Development Status :: 3 - Alpha` in
   `pyproject.toml`, beside `version = "1.0.0b1"`.

---

## 4. What this product is not

Fixed, and each line is refused for a reason rather than for now.

- **Not a migration analyzer.** It reports a tenant. It does not score its
  readiness to become a different tenant.
- **It does not infer on-premises state.** It evaluates the Microsoft 365
  tenant that exists today, per [SCOPE.md](SCOPE.md).
- **Not a remediator, and never a writer.** No `--fix`, no write path. A tool
  that judges and repairs destroys the evidence for its own finding.
- **Not a score.** No number, no grade, no percentage. A score is the green box
  the product exists to argue with.
- **It never adds different `basis` types together.** A documented limit and a
  convention are not two of the same thing, and a total that mixes them is a
  claim nobody can check.
- **Not a replacement for Purview, SharePoint Advanced Management or
  Defender.** Those enforce. This one explains, and cites.
- **It never calls `unknown` a pass.** Six outcomes exist so that "we could not
  read this" has somewhere to go that is not "fine".

---

## 5. Roadmap, by capability

### A. Collection
Application authentication; group expansion; tenant-wide coverage that states
what it missed; the three collector modes currently unreachable from the CLI.

*Today: one delegated identity, 47 of 53 sites, six refusals recorded per
document and nowhere per run.*

### B. Governance coverage
Finish SharePoint Online. Decide when a second service opens, and open exactly
one. **Three products at once, none of them deep, is the failure mode.**

*Today: 18 rules, one service, three resource types, three of five basis types
in use.*

### C. Assessment mode
An importer, after a real export format has been read. Not before.

*Today: documented in SCOPE.md, supported by the schema, rendered by the
report, and not implemented.*

### D. Explainability
Provenance, basis, rule version and evidence version all travel with a
finding already. A `why`/trace command only if somebody's real question needs
it.

*Today: the strongest part of the product.*

### E. Reporting
Markdown, JSON, HTML exist. Make `report` accept what `evaluate` produces.
SARIF only after the `kind`-to-`level` constraint is answered from the
normative text.

### F. Historical comparison
A snapshot that is a run and not a file somebody kept; `diff` over a tenant;
regressions; and the distinction between *the tenant changed* and *the rule
changed*, which `diff` already carries for one resource.

### G. Operational maturity
Packaging and a real release; schema `$id`s that resolve; migrations; an
upgrade path; a compatibility matrix; a clean install proven somewhere that is
not this laptop.

---

## 6. Must / Should / Later / Never

### The test every P0 has to pass

> **If this does not exist, can somebody use the product consistently?**
>
> **Yes** — it is not P0, however valuable it is.
> **No** — it is P0.

Applied honestly, it moved two items out of the list and made one of them
larger. What follows is the test, item by item, so the demotions are arguable
rather than asserted.

| Candidate | Without it, can the product be used consistently? | Verdict |
|---|---|---|
| The loop closing at tenant scale | **No.** `evaluate` emits a shape its own sibling commands reject. | **P0** |
| A self-contained installation | **No.** The product is not relocatable: nine of ten commands fail outside a clone. | **P0** |
| A clean install proven off this machine | **No.** It is the only thing that can establish the above. | **P0** |
| `doctor` reporting the default profile truthfully | **No.** It misstates the configuration and then says nothing is broken. | **P0** |
| `collect spfx` | **No.** A rule and a profile exist that no command can feed. | **P0** |
| Schema `$id`s resolving | **Yes.** Validation never fetches them; everything works. | Should |
| Application authentication | **Yes.** Delegated collection works and declares its own limits. | P1 |

The identity question has its own test, and it is not the same one:

> **Is the product consistent with the identity it used?**

Today it is. Every document records `identity_kind`, coverage and provenance,
so a result is reproducible within the scope that produced it. Application
authentication widens the scope. It does not repair an inconsistency.

### Must before 1.0 — P0

**1. The full loop, at tenant scale.** Today the product does:

```
collect → evaluate
```

The loop it promises is:

```
collect → evaluate → save run → report → diff
```

`report` and `diff` must consume a complete run, not one resource at a time.
Until they do, **reproducibility is a design goal and not a property**, and it
is the sentence the whole project rests on.

Run-level coverage belongs here rather than with application authentication. A
report over 47 sites that says 47 without saying "of 53" is the inconsistency;
a wider identity would make it rarer without making it honest.

**2. Self-contained installation.** The product is not relocatable. That is
the finding, and it is larger than "it is not on PyPI".

`pip install` must produce a working tool that depends on nothing in the
repository tree. Closed when all six hold, checked from a directory that is
not a checkout:

- `doctor` runs and finds what it is checking;
- `list-rules` runs;
- `validate` finds the schemas;
- `evaluate` finds the profiles and the rules;
- `collect` finds the collectors;
- **no path resolves against the repository.**

Two separate mechanisms break it, and the second is the more dangerous:

1. **Defaults relative to the working directory.** `DEFAULT_RULES =
   Path("rules")`, `DEFAULT_PROFILE = Path("profiles/default.yaml")`, and
   `doctor --root` defaulting to `Path(".")`. These fail loudly, wherever you
   stand.
2. **A path relative to the module that assumes the source layout.**
   `COLLECTOR = Path(__file__).resolve().parents[2] / "collectors" / ...`
   resolves to the repository root from `src/m365_governance/`, and to
   `lib/python3.14/collectors/...` from site-packages. It *looks*
   relocatable, because it is anchored to `__file__` rather than to the
   working directory, and it silently points somewhere plausible that does
   not exist.

**Only after this does PyPI mean anything.** Publishing the package as it
stands would ship a CLI that cannot find its own rules. The tag and the
release follow packaging; they do not substitute for it.

**3. A clean install proven somewhere that is not this laptop.** It is the
only evidence that item 2 is closed, and it is how item 2 was found in the
first place.

**4. `doctor` tells the truth about the default profile.** It reports `0 rules
selected` for the profile that selects all sixteen, then prints "Nothing is
broken". A diagnostic that misreports the configuration is worse than no
diagnostic: it is consulted precisely when somebody is already unsure.

**5. `collect spfx`.** `SpfxCatalog` and `SpfxPages` are collector modes with
a rule and a profile, and no command can produce their evidence. A capability
only its author can reach is not a capability.

### Must before 1.0 — P1

**6. Application authentication.** **Demoted from P0 by the test, and the
demotion is arguable.**

Against: six of 53 sites refused the delegated collector and produced no
evidence at all, which looks like an inconsistency.

For: the product is *consistent* under a delegated identity. It reads what one
person can read, records `identity_kind: delegated`, and says so in every
report. The findings are narrower, not wrong. What is inconsistent is a run
that silently reports 47 of 53, and that is fixed by run-level coverage in
item 1, not by a wider identity. Application authentication changes the
**scale** of the product; 1.0 is about whether the product is **whole**.

**7. Assessment mode — the pipeline, not the adapters.** Define and build:

```
import → normalize → evaluate
```

ShareGate, CSV and the rest are adapters onto a pipeline that must exist
before any of them can be judged. Building an adapter first would settle the
pipeline's shape by accident, around whichever export happened to be read
first.

### Should before 1.0
High value, does not block the word stable.

- **Schema `$id`s resolve**, or become identifiers that do not promise a URL.
  Nothing breaks today; a project whose argument is verifiable sources
  publishing two that 404 is a credibility cost rather than a functional one.
- **`Development Status` classifier matches the version.** It reads `3 -
  Alpha` beside `1.0.0b1`.
- **Group expansion.** It turns bounds into counts and will move findings in
  both directions.
- **HTML designed for a reader who did not write the rules.**
- **Public wording that matches the rule set.** The five basis types stay; the
  description changes. "The rule model defines five truth categories. The
  current rule set exercises three of them." Factual, and promises nothing the
  product does not demonstrate.
- **`--fail-on` default reconsidered.** Silence by default, in a tool built
  against silent passes.

### Later
Legitimate, and not 1.0.

- **Import adapters.** After the pipeline exists, and only once a real
  ShareGate, SMAT or CSV export has been read rather than imagined.
- **Entra.** The most likely second service: it is where identity lives, and
  most SharePoint governance questions end there.
- **Teams**, then **Exchange**. One at a time.
- **SARIF**, once the `kind`-to-`level` constraint is answered.
- **`new-rule` scaffolding.** Useful once rules come from outside.

### Never
Contradicts the model.

- **Scoring.** Any single number over mixed `basis` types.
- **Remediation.** Any write path, under any flag.
- **A migration destination.** Recommending where content should go is a claim
  about a tenant that does not exist.
- **`benchmark` against other tenants.** It would require data this project
  refuses to hold, and it answers "are we normal", not "is this true".

---

## 7. Release sequence

Each release answers one question: **what new promise can a user rely on?**

### `1.0.0-beta.2` — the beta becomes a product you can install
*Promise: `pip install` gives you a working tool, and `doctor` tells the truth
about it.*
Package data, so an installed copy carries its rules, profiles, schemas and
collector. A clean install proven off this machine. The `doctor` defect, the
`stats` column, the classifier. Then a tag and a release. No new capability.

### `1.0.0-beta.3` — the loop closes
*Promise: you can evaluate a whole tenant, keep the result, and reopen it.*
`report` and `diff` over the many-resource shape. `collect spfx`. Coverage at
the run level.

### `1.0.0-rc.1` — scope frozen
*Promise: what is here is what 1.0 will contain.*
Application authentication, and the `import → normalize → evaluate` pipeline
with no adapter yet. No new capability after this point; only defects.
Used against a tenant that is not the validating one.

### `1.0.0` — stability
*Promise: rules, evidence and reports are stable, versioned, and upgradeable.*
Documented upgrade path, compatibility matrix, and the acceptance criteria in
§8 all met.

### `1.1` — the next capability
Group expansion, or Entra. **One of them.**

---

## 8. Acceptance criteria for 1.0

Objective, each one checkable by running something.

1. Every collector mode declared as supported has been run against a real
   tenant, and the evidence it produced is in the repository as a fixture with
   the tenant data removed.
2. Every collector mode declared as supported is reachable from the CLI.
3. Zero skipped tests. Coverage at or above 90 per cent, measured with
   branches.
4. Both schemas carry a version, and their `$id` resolves.
5. A documented upgrade path from every published schema version, with a test
   that reads a document written against the previous one.
6. No rule without either tenant-observed evidence or a fixture that exercises
   every one of its outcomes.
7. No integration built on a value absent from a recorded normative source.
   Enforced by `tests/external/`.
8. Read-only proven: CI parses the collector and fails on any mutating verb,
   and the limits of that proof are documented.
9. Every example in the README reproduces, verified by `tools/examples.py
   --check` in CI.
10. **A clean install is a permanent gate, not a one-off check.** CI builds
    the artifact, installs it into an empty environment, changes to a
    directory that is not a checkout, and runs the product there: `doctor`,
    `list-rules`, `validate`, and an `evaluate` over a packaged fixture. It
    fails on the first path that reaches back into the repository.

    This is the gate that found the defect, and it is the only kind that could
    have. Every existing test runs from the repository root, so every existing
    test agreed the product worked. **A suite that only runs where the source
    lives cannot detect that the product does not run anywhere else.**

11. A clean install from the published artifact, on a machine that has never
    held this repository, producing a report from a fixture.
12. Documentation consistent with behaviour: no capability described that
    running the product contradicts. This document's §3 is the template.
13. A release candidate used against a tenant that is not the validating one.

---

## 9. Open decisions

- **Decided, and recorded here so it is not reopened: the `requirement` and
  `opinion` types stay.** An empty category is not a wrong one. It reports that
  the rule set does not yet cover a claim of that kind, which is what the model
  is for. Only the public wording changes. The question that remains is a
  different one: **is there a Microsoft obligation this product could actually
  observe?** A `requirement` needs a claim the product enforces *and* evidence
  a collector can read, and it is not obvious that the intersection is
  non-empty.
- **What is a snapshot?** `diff` compares two files. Whether the product owns a
  store, or stays a tool that reads whatever you kept, decides most of
  capability F.
- **Which `kind` values may SARIF pair with a non-`none` `level`?** Recorded as
  unverified in `tests/external/sarif-2.1.0.json`. If a non-`fail` kind is
  forced to `level: none`, `unknown` reaches a pipeline UI with no severity,
  and the slice may not be worth building.
- **Should `--fail-on` default to `never`?**
- **How does a profile override a threshold** without restating a rule? Open
  since the first profile, and it is what stops the second profile of a kind
  from existing.
- **When does the second service open, and is it Entra?**
- **What ships inside the package, and what stays a repository artifact?**
  Rules and profiles are the product's content and are also the thing users
  are invited to fork and replace. Shipping them makes an install work out of
  the box; shipping them also means a rule update needs a release. A default
  set inside the package with an override path is the obvious answer and it
  has not been designed.
- **Does an importer belong in this repository at all**, or is an adapter that
  emits the schema better off separate, so that a broken export is not a
  broken release here?
