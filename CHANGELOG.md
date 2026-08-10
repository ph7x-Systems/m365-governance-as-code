# Changelog

Versions follow [semantic versioning](https://semver.org). Below `1.0.0` the
interfaces may change; when they do, it is said here.

Rules carry their own versions, independently of this file. See
[docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md).

---

## Unreleased

### Removed

- **The support link, from this repository.** The badge, the section in the
  README, the paragraph in CONTRIBUTING and `.github/FUNDING.yml` are gone. The
  product explains the software, documents how it is licensed today, and asks
  for nothing; support for the writing and the research lives on ph7x.com,
  where what is being supported is the publishing.

  It was an allowed exception in the strategy guard until now, and that
  exception is what made the ambiguity possible: *the coffee link stays* was
  read as everywhere rather than as on the site. It is a forbidden pattern now.
  A named exception is a decision somebody has to remember; a forbidden pattern
  is one they cannot forget.

### Added

- **A result carries the rule's own title.** An id identifies; a title says
  what was checked, and it is what a person cites in a sentence.

## Unreleased

P0.1 from [docs/PRODUCT-STRATEGY.md](docs/PRODUCT-STRATEGY.md): self-contained
installation. Before this, `pip install` produced a command-line tool with none
of its own content, and `explain` was the only command of ten that worked
outside a checkout.

### Added

- **The product ships inside the package.** `rules/`, `profiles/`,
  `schemas/`, `collectors/` and `fixtures/` moved to
  `src/m365_governance/data/` and are declared as package data, reached
  through `importlib.resources`.
- **A clean-install job in CI.** It builds the wheel, checks the wheel
  actually carries the content, installs it into an empty environment,
  changes to a directory that is not a checkout, and runs `doctor`,
  `list-rules`, `validate`, `evaluate` and `collect --dry-run` there. A final
  step fails if any path in the output reaches back into the workspace.
- **`--rules` and `--profile` are overrides, not defaults.** Omitted, the
  packaged set is used. Supplied, it is replaced entirely. **There is never a
  merge**, and every report now carries a `Rules:` line saying which of the
  two produced the findings.
- `resources.py`, `tests/test_resources.py`, and a `Installation` group in
  `doctor` reporting whether the installed package contains its own content.

### Fixed

- **`doctor` reported the default profile as selecting 0 of 16 rules** and
  then printed "Nothing is broken". A profile with no `rules` key selects
  every rule; the count read the raw value.
- **Two path defects, and the second was the dangerous one.**
  `Path("rules")` resolved against the working directory and failed loudly.
  `Path(__file__).resolve().parents[2] / "collectors"` was anchored to
  `__file__`, was correct from `src/`, and pointed at
  `lib/python3.x/collectors` from site-packages: plausible, and absent. A
  test now walks the AST of every module in the package and fails on any
  `.parents[n]`, rather than searching the text, because two modules describe
  the defect in prose so that it is not repeated.
- `Development Status` classifier read `3 - Alpha` beside `version = 1.0.0b1`.

Epic B opened on the `1.0.0-beta.1` baseline. See
[docs/EPIC-B.md](docs/EPIC-B.md). Milestone A is closed and does not reopen.

### Added

- **Facts before design. Schema before mapping. Tenant before rule.** Written
  into [CONTRIBUTING.md](CONTRIBUTING.md) as a rule of execution rather than an
  observation: no external behaviour is implemented from memory, from a
  plausible name, or from secondary documentation, when a schema, an assembly
  or a specification exists and can be read. Where the normative source does
  not answer, the product declares the gap instead of filling it by
  plausibility.
- **`tests/external/`**, where those readings are recorded with their source
  and the date they were checked, and `tests/test_external_facts.py`, which
  enforces that every recorded fact is attributed, that a declared gap carries
  a usable reason, and that no code reaches for a value the recording does not
  contain.
- **The PnP 3.3.0 property sets**, read from the loaded assemblies: 490
  properties across four types. Every `-Includes` clause in the collector is
  now checked against them. Injecting `SharingCapability` into the
  classification clause fails the build, which is the defect that reached a
  tenant before this existed.
- **The SARIF 2.1.0 enums**, read from the schema. `result.kind` permits six
  values and `result.level` four. A prose summary of the same specification
  offered `redirect` and `hotspot`; the enum contains neither, and a test now
  says so. The kind-to-level constraint is recorded as unverified, and a test
  asserts no SARIF mapping exists until it is answered.

### Carried debt

- `Coverage` and `Collector is read-only` run only on the 3.13 matrix entry,
  so those two gates have the availability of a matrix of one. On 2026-08-06
  three runs were cancelled with zero steps executed and, when the incident
  eased, 3.11 and 3.12 passed while 3.13 did not, leaving exactly those two
  unproven. They passed on the next attempt with no change to the repository.
  Registered, deliberately not fixed: what was observed was runner
  availability, not a defect in the design.

---

## 1.0.0-beta.1

Classification, and the end of Epic A.

The eighth and last vertical slice of the SharePoint milestone, and the first
release the model is not expected to move under. See
[docs/MILESTONE-A.md](docs/MILESTONE-A.md) for what closing a service end to
end actually cost: eight slices, sixteen rules, and nine defects that only a
real tenant found.

### Added

- **`Classification` collector mode.** Reads the sensitivity label, the older
  classification string and the group connection from the site itself, with no
  administrative right required. Ten modes now.
- **`collect classification`.** No new command and no new profile: the three
  rules that read this evidence are the only ones that read it, so a profile
  naming them would repeat what the evidence already says.
- **SPO-CLASS-001** (`documented-guidance`), a site with neither a sensitivity
  label nor a classification string. Microsoft's own deployment model names the
  unlabelled site as the thing to go and find, which is what makes the basis
  documented rather than ours.
- **SPO-CLASS-002** (`convention`), a site carrying a label whose name could
  not be resolved. Classified, and no report can say as what.
- **SPO-CLASS-003** (`convention`), a group-connected site with no label, where
  privacy and external user access rest on settings nothing pins.
- Eight fixtures and the outcome matrix for all three rules, including the
  `invalid-evidence` path for each.

### Changed

- **An empty label is an observation, not a gap.** The first version of the
  collector reported an empty `SensitivityLabelId` as `missing` and then
  derived `classified: false` from it — an answer built out of three
  admissions of ignorance. A property that loaded and came back empty is
  SharePoint saying there is no label; only a property that could not be read
  is a gap. Run against 47 sites, the difference is between "none of these
  sites is classified" and "nothing here is known".
- A profile with no `rules` key selects everything, and the slice-pairing test
  now reads it that way. It previously required the key, which would have let
  a slice paired with `default` pass by evaluating nothing at all.

### Not done, on purpose

- **No fourth classification rule.** One of type `opinion` was allowed on
  condition that a real case existed. The validating tenant has no labels and
  no classification strings, so there was nothing to have an opinion about.
- **No `IsTeamsConnected`.** It is a property of the tenant record and PnP
  refuses to switch to the administration context after a device login.
  `GroupId` answers the weaker question with no administrative right at all.
- **No site privacy.** `PrivacySetting` is not a property of `SPOSite`. It was
  specified and it is not in the product.
- **Classification is never inferred from a site name.** A test asserts that no
  classification rule reads a title, a url or a template.

---

## 0.9.0-alpha

Activity, and the date that decides whether the rule means anything.

**Breaking changes:** none.

### Three dates, and only one of them is about people

| Property | Moves when |
|---|---|
| `LastItemModifiedDate` | anything changes an item, including a system process |
| `LastItemUserModifiedDate` | a person changes something |
| `Created` | for a site that never had a first change |

On the tenant, all three sites reported `LastItemModifiedDate` as **the day of
collection**. A search crawl, a sync or a retention job had touched every one
of them. The same three on `LastItemUserModifiedDate`:

```
home       10 days
training  440 days
root      573 days
```

A rule reading the first field reports nothing, confidently, for ever. This
one reads the second.

### Locked and archived are decisions, not accidents

`activity.changeable` is derived from `LockState` and `ArchiveStatus`, and it
is the rule's applicability. A site nobody may write to and a site nobody
wants are different findings, and reporting them together buries the decision
among the accidents. Both produce `not-applicable`, which is not a pass.

### `SPO-ACTIVITY-001`

`convention`, 365 days. Microsoft publishes no such period and provides site
lifecycle policies precisely so each organisation picks its own; the year is
ours and says so.

It reads writes and never reads, and the limitation says that too: a reference
site hundreds of people open and nobody edits fails this rule, and failing it
is the correct answer to the question asked.

### Coverage

Measured for the first time, and it found something. The bounded comparison
sat at 86 per cent with nearly the whole table from `ARCHITECTURE.md` never
executed. `tests/test_bounded.py` is that table, one case per cell. The engine
is now at 97 per cent and the project at 91, with a floor in CI.

### The read-only check is a step

It was a job, which meant a second runner and a second `actions/checkout` to
resolve. GitHub failed to resolve it twice in a row while the other job
resolved the same action in the same run. Three seconds of checking was not
worth a whole job's exposure.

316 tests.

---

## 0.8.0-alpha

SPFx, in two modes, and three rules that turned out to be unwritable.

**Breaking changes:** none.

### Two levels, because one of them is expensive

`SpfxCatalog` reads an app catalog in one call. `SpfxPages` opens every page
on a site and is opt-in, with `-MaxPages` and `-ModifiedSince` to bound it.
Against a real tenant: 18.0 seconds for the catalog, 5.7 seconds for two
pages.

A page that was skipped, capped or unreadable is never a page without
components. The evidence states which of the three it was, and the component
count is `partial` unless every page was opened.

### Three rules that cannot be written, and why

**No rule about an unused solution.** A component on a page reports a
`web_part_id`; a solution in the catalog reports the package id. On the tenant
those are `24cc778a-…` and `9a131334-…` for the same web part, and
`AppMetadata` does not list the components a package contains. The two cannot
be joined without matching on titles, and matching on titles is a guess in
whatever language somebody named the package in.

**No rule about a component without a package**, for the same reason. Every
component would look unidentified and the rule would fire on all of them for
ever.

**No rule about tenant-wide deployment.** `AppMetadata` has exactly seven
properties and none is that flag. It lives in the Tenant Wide Extensions list,
which this collector does not read.

All three are recorded in `profiles/spfx.yaml`, where somebody looking for
them will be.

### The one that could be written

`SPO-SPFX-001`, `convention`: a solution installed at an older version than
the catalog holds. Two version numbers the catalog reports side by side, and a
reader can check the finding against the numbers printed beside it.

### A collector that could not count

The first run reported 9 pages, 8 inspected and 7 that could not be opened.
Fifteen outcomes for nine pages. Every one of those numbers was believable on
its own, and a report built on them would have been believable too.

The collector now reconciles its own counting, and when the total does not
add up it marks the affected facts `invalid` with the arithmetic in the
detail. `invalid` rather than `unknown`, because the fix is in the collector
and not in another collection.

270 tests.

---

## 0.7.0-alpha

Modernity, in the order that keeps working: fact, schema, tenant, rule.

**Breaking changes:** none.

### The facts, first

A `Modernity` collector mode reads what the product says about how a site is
built: template and configuration, master page, alternate stylesheet, the
feature identifiers enabled at web and site scope, and two page counts.

It reads nothing as "modern" or "classic". That reading is a rule's job, next
to a source.

### Then the tenant, and two rules it stopped from being wrong

**`CustomMasterUrl` is set on every site, to the default.** The tenant returned
`/_catalogs/masterpage/seattle.master` for both `MasterUrl` and
`CustomMasterUrl`. A rule checking that a custom master page is "set" would
have fired on every site in every tenant, forever, and looked plausible doing
it.

**The path carries the site.** On the root site the default master page reads
`/_catalogs/masterpage/seattle.master`; on a subsite the same default reads
`/sites/x/_catalogs/masterpage/seattle.master`. Comparing paths against a
known default would report every site that is not the root. The collector now
derives the file name, and a test pins the subsite case.

### Then the rules

| id | basis | Reads |
|---|---|---|
| `SPO-MODERN-001` | `documented-guidance` | The classic publishing feature, by the identifier Microsoft publishes |
| `SPO-MODERN-003` | `convention` | A master page that is not one of the two SharePoint provides |
| `SPO-MODERN-004` | `convention` | An alternate stylesheet loaded into every page |

The publishing identifier is quoted from Microsoft's own feature table with
the date it was checked, and lives in the rule rather than in the collector: a
GUID meaning something is a documented claim, and documented claims belong
next to their source.

### The rule that was not written

There is no rule counting classic pages. The collector reports
`in_library_not_returned_as_modern`, and the name is the point: a page can be
absent from the modern API's list for reasons other than being classic, and
this collector does not know which. Naming that count "classic pages" would be
the inference this project exists to refuse.

A test rejects any rule that reads a path called `classic_pages`.

### Also

The `list-rules` count in the tests is derived rather than pinned. It was a
literal, it broke on every rule added, and it taught nobody anything each
time.

258 tests.

---

## 0.6.1-alpha

The classification, run against 23 real lists, and corrected twice by them.

**Breaking changes:** none. `SPO-*` rules are untouched.

### What the tenant said

23 lists, 19.7 seconds, all valid against the schema. The previous run
returned 8: the collector used to skip hidden lists, and dropping that filter
found 15 more.

Every list classified. None came back `unknown`, and every `content` verdict
rests on three observed `false` values rather than on absence.

| | |
|---|---|
| `system` | 18 |
| `content` | 3 |
| `application` | 2 |

### Two corrections the data forced

**`is_application` now outranks `is_system`.** `Site Pages` and `Site Assets`
come back with both flags true. They were provisioned by the platform and they
hold the pages of the site. The original order called them plumbing and moved
a site's own pages down the report.

**A stated justification was false.** The precedence comment claimed that
"Style Library and Form Templates are catalogs that are not marked as system
lists". Style Library is `is_catalog` **and** `is_system`; Form Templates is
`is_system` and not a catalog. The order still produced the right answer for
both, which is exactly why a wrong reason written next to a right answer
survives review. It is corrected, and the real values are quoted.

### A limitation, stated rather than patched

These flags answer "who provisioned this", not "is this worth reading".
`App Packages`, the site collection app catalog, comes back as none of the
three and is therefore `content`. That is wrong in every sense except the one
that matters here: it is what the product says. The alternative is matching on
a title, and matching on a title is how a classifier starts lying in a
language it was never tested in.

### Verified on real data

A catalog carrying a scope count above the hard limit still counts in the
`Fail` total at the top of the report and prints under its own heading at the
bottom. The profile moved 18 lists down the page and removed none.

243 tests.

---

## 0.6.0-alpha

Lists get a class, profiles get to use it, and `evaluate` reads a directory.

**Breaking changes:** none.

### Classification

A collector now records what SharePoint says about a list: `IsCatalog`,
`IsSystemList`, `IsApplicationList`, `Hidden`, `BaseTemplate`. All five exist
on the CSOM type and all five are the product's own answer.

**The collector does not classify and no longer filters.** It used to skip
hidden lists, which was the collector deciding what mattered, and it decided
wrong: three of the eight it returned from a real tenant were catalogs anyway.

The classification is a derivation with one job, an order of precedence, and
it lives in one reviewable function: catalog, then system, then application,
then content. Absence of all three is `unknown` and never `content`, because a
list nobody classified is a list nobody looked at.

### Profiles set aside, they do not exclude

```yaml
set_aside_classes:
  - system
```

A set-aside resource is still collected, still evaluated, still counted in the
summary, and still printed under its own heading at the end.

The key is not called `exclude`, and a test enforces that no profile carries
one. The reason is in the test: a catalog holding 61,400 unique permission
scopes is over a hard product limit whoever created it. Under exclusion that
finding disappears. Under set-aside it appears at the bottom, counted in the
`Fail` total at the top.

### `evaluate` reads a directory

```bash
m365-governance evaluate --profile profiles/capacity.yaml --evidence evidence/
```

The report opens with what was observed, by class, and how many the profile
moved down the page:

```
5 resources observed
  application     1
  content         1
  system          3
  set aside by profile: 3, carrying 5 answers. Reported below, not removed.
```

The shape follows what was asked for rather than how many files happened to be
there: a path to a file renders one report, a path to a directory renders a
collection, and a directory with one document in it today and three tomorrow
does not change what a pipeline parses.

### Still not written

The anonymous-link expiry rule. `AnonymousLinkExpirationInDays = 0` remains
ambiguous: the tenant returned 0 on a site with sharing disabled entirely,
where 0 may simply mean not applicable. Recorded as unknown semantics until
documentation or a tenant with the setting active proves the meaning.

239 tests.

---

## 0.5.1-alpha

Validated against a live tenant, read-only. Four defects, all of them
invisible offline.

**Breaking changes:** `collect sharing` now needs `--tenant-url` as well as
`--site-url`. `SPO-SHARE-002` moves to v2.0.

### What the run found

**`SharingCapability` is not a property of a site.** `Get-PnPSite -Includes
SharingCapability` fails at the parameter set: it is a tenant property *about*
a site, read through `Get-PnPTenantSite`, which needs an administrative
connection. The mode had never worked and could not have.

**`DefaultSharingLinkType` returns `None` on a site that sets no default of
its own**, meaning it follows the tenant. The rule compared it against
`AnonymousAccess` and would have returned **pass** while knowing nothing: the
inherited default could be exactly that. There is now an
`effective_default_link_type` fact, missing when the site inherits, and the
rule returns `unknown`.

Every one of the 53 sites in the tenant reported `None`.

**The slice-to-profile pairing was wrong.** `collect sites` gathers inventory,
not owners, and against the `ownership` profile it produced 106 `unknown`
results across 53 sites. Every one honest, none useful. A test now evaluates a
slice-shaped document with the profile the slice names and fails if nothing
but `unknown` comes back.

**Nothing proved that `AnonymousLinkExpirationInDays = 0` means no expiry.**
The tenant returned 0 on a site with sharing disabled entirely, where 0 may
simply mean not applicable. The expiry rule stays unwritten.

### Confirmed against the tenant

| | |
|---|---|
| `SharingCapabilities` | `Disabled`, and the enum is the one the rule compares against |
| `SharingLinkType` | `None`, `Direct`, `Internal`, `AnonymousAccess` |
| `StorageUsageCurrent` / `StorageQuota` | both MB, `Int64`. A 25 TB quota reads as 26214400 |
| `LockState` | a string, `Unlock` |
| `GroupId` | all zeros when not group-connected, so the derivation holds |
| `PrincipalType` | `User` for a direct administrator |

63 evidence documents, all valid against the schema. None entered Git.

223 tests.

---

## 0.5.0-alpha

Four more rules, four profiles, and a `collect` command that judges nothing.

**Breaking changes:** none.

### Rules

| id | basis | Reads |
|---|---|---|
| `SPO-SITE-002` | `convention` | Whether any administrator is a person rather than a group |
| `SPO-SITE-003` | `convention` | Storage above 90 per cent of quota. The number is ours and says so |
| `SPO-SHARE-001` | `convention` | A site that permits Anyone links |
| `SPO-SHARE-002` | `documented-guidance` | The Anyone link as the site default |

The two sharing rules have different bases on purpose. Microsoft permits
Anyone links, documents them, and offers them as one of four options: judging
a site for allowing them is our position. Microsoft's own page on the default
link type says "set the default type of link to something more restrictive":
that is guidance, quoted, with the date it was checked.

The enum values were read out of the loaded PnP assemblies rather than
guessed. `ExternalUserAndGuestSharing` and `AnonymousAccess` are what the
product uses, and a rule that had guessed `Anyone` would have matched nothing
while looking correct.

### Profiles

`ownership`, `sharing` and `capacity`, each paired with the collection that
answers it. Running every rule against a sharing snapshot is not wrong and
produces four `unknown` results per site for facts nobody requested. That is
honest, and it is noise, and noise is how the one line that mattered gets
skimmed past.

A test asserts that selecting fewer rules removes `unknown` and never a
`fail`, and another that no profile carries anything beyond a selection.

### `collect`

```bash
m365-governance collect sharing --site-url ... --client-id ... --output ...
```

Four slices: `sites`, `owners`, `sharing`, `permissions`. It runs the
PowerShell collector, reports how long it took and how many documents it
wrote, and names the profile that reads them. It evaluates nothing, and a test
asserts the module cannot: it does not import the engine.

`--dry-run` prints the command and reaches no tenant.

### Evidence schema 1.2.0

An aggregate fact may carry `direct_count` and `group_count`. They answer a
different question from the total: the total asks how many administrators
there are, these ask whether any of them is a person somebody could ring.

209 tests.

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
`Connect-PnPOnline` needs a client id this collector supplies explicitly, and a
CSOM property read through the context returns null without raising.

> Corrected on 2026-08-10: this entry said "since PnP 2.99". No such release
> exists — the changelog goes 2.12.0, then 3.x — and the shared PnP Management
> Shell application was removed on 9 September 2024. The entry is corrected in
> place rather than rewritten silently, because a released note that quietly
> changes its facts is worth less than one that says what it got wrong.
