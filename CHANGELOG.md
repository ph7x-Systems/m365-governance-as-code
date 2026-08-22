# Changelog

Versions follow [semantic versioning](https://semver.org). Below `1.0.0` the
interfaces may change; when they do, it is said here.

Rules carry their own versions, independently of this file. See
[docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md).

---

## Unreleased

Nothing yet. Work merged after `1.0.0b7` is recorded here and is not published,
not documented on the site, and not `tested_with` anything until it ships in a
release of its own.

---

## 1.0.0b7

The release that makes the desktop path real: evidence becomes a canonical
bundle without reaching a tenant again, and three observation surfaces arrive
that decide nothing on purpose.

Every claim below is classified. **New capability** is something the engine
could not do before. **Behaviour change** is something it did differently.
**Contract version change** is a shape a consumer validates against.
**Known limitation** is a boundary this version has and keeps. **Not
established** is something nobody has observed, named here so that its absence
is not read as an absence of the problem.

### New capability

- **`evaluate --bundle` writes the folder a consumer opens, from evidence that
  already exists.** The portable folder was reachable only through `run`, which
  collects first, so somebody holding good evidence — a previous collection, a
  pipeline, a colleague's export — had to reach the tenant again to obtain the
  packaging. What was read and how it is carried are different questions. It is
  the same writer `run` calls, asserted against that writer's own bytes rather
  than against a shape described in a test, and it reaches no tenant: the whole
  desktop experience is provable offline against frozen evidence.

- **Microsoft 365 licensing evidence.** `collect licensing` reads what is
  assigned in a tenant and whether the usage reports are permitted to name the
  people who hold it, through Microsoft Graph rather than PnP. Four independent
  coverage areas — `assignment`, `usage_identity`, `usage`, `dependency` — and
  completing one implies nothing about the others. Microsoft conceals user names
  in usage reports by default and the same setting reaches Graph, so in a default
  tenant **usage cannot be joined to a user**; the reports also cover a window,
  arrive 24 to 72 hours late, and lose a deleted user's data within 30 days. Each
  of those is a fact in the evidence rather than a footnote.

- **Page-execution and customization surfaces.** `collect customization` reads
  the custom script setting where a tenant-scoped read was made, whether the
  identity holds `AddAndCustomizePages`, whether the Site Pages web feature is
  present, whether the Site Pages library is readable, and whether it carries
  unique permissions. It answers *what surfaces are observable here* and refuses
  *is this site safe*.

- **Agent governance: a count that travels with the population it counts.**
  `count: 3` reads as *this tenant has three agents* to anybody who did not write
  the collector, and it is not that: it is three `.agent` files in one site's Site
  Assets library, enumerated by one identity at one moment. The evidence carries
  `population`, `acquisition_method` and `populations_not_observed`, the last
  naming what this method cannot reach — an agent built in Agent Builder is not a
  file in a library. **An inventory surface defines a population; it does not
  define existence outside that population.**

- **Microsoft Entra ID, starting with the access-policy surface.**
  `collect conditional-access` reads Conditional Access policies, the named
  locations they reference and the Security Defaults state in one session, and is
  the first collector here that does not run PowerShell. An area that could not be
  read produces a document carrying the state and the reason: writing nothing
  would leave a directory indistinguishable from a tenant with no Conditional
  Access at all, and a rule over that would pass.

- **`setup`, `connect` and `run`.** The journey is three commands: `setup`
  prepares the machine and writes the target down, `connect` proves the identity
  can work here, `run` collects, evaluates and reports. Choosing among ten slices
  was a decision this engine can make from the target it was given.
  `m365-governance.toml` carries the tenant and site addresses, the application
  registration and the authentication mode; the command line always wins, the file
  that was read is named on every run, and a key naming a credential is refused
  rather than ignored.

- **`connect` answers whether an identity can work here, not only whether a
  sign-in succeeded.** `Connect-PnPOnline` succeeds with zero permissions granted,
  so one read is attempted and reported separately, and `not-attempted` is never
  reported as established. A certificate now actually reaches the tenant: the
  arguments were validated and then dropped, so the one command whose purpose is
  to prove an application registration could not prove it for the identity an
  unattended run uses.

- **`capabilities` publishes what this engine can do**, as a contract rather
  than as prose, and `--questions` projects the same document as *what can it
  tell me* rather than *what does it touch*.

- **`--period` on `collect`**, so the licensing usage window can be asked for at
  all. Microsoft's four values, and no default invented here.

- **`doctor` names the modules a collector needs**, with the acquisition surface
  each one serves and the exact `Install-Module` command, so a machine that cannot
  run a collector says which install is missing rather than reporting an empty
  tenant. It also says how to install PowerShell 7.

### Behaviour change

- **The bundle is produced by the engine being published**, not by whatever
  `m365-governance` the PATH resolves to. It resolved to nothing here and every
  sample was skipped in silence, because a fixture that failed to evaluate was a
  `continue`. A consumer had already vendored a bundle three samples wide. A
  skipped fixture now fails the publish, and the bundle carries seventy-one.

- **A shipped assessment its own verifier refused.** An assessment's identity is
  derived from the bytes of its parts, the cascade rewrote the contract each part
  declares, and the document reached a consumer carrying digests of what it used
  to say. Both assessment fixtures are now verified, with the verifier a consumer
  uses; before this, one of the two was read by no test at all.

- **A path that is not there is a refusal, not a result.** `evaluate`, `assess`,
  `stats`, `report`, `verify` and `diff` raised `FileNotFoundError` under exit
  `1` — the code reserved for a negative governance result — so a typed path
  reached a pipeline as a failing rule. It is exit `2` and one sentence.

- **A report names the resource it is about.** The header read `resource["id"]`,
  a key no evidence document has ever carried, so every markdown report printed
  `<unknown>` beside a title that had the name in it all along.

- **A rule now has to match the workload as well as the resource type.**
  `tenant` is a type name in every workload, so a SharePoint tenant rule applied
  to an Entra tenant document the moment a second workload existed.

- **An interactive sign-in no longer goes wherever the browser happens to be
  signed in.** The collector resolves which directory owns an address before
  signing in; where nothing owned it, it signed in anyway and reported what it
  found in an unrelated directory as an answer about the address that was typed.
  Refused now, for every mode. A certificate proceeds: `-Tenant` names the
  directory.

- **A slice that will not be attempted is reported, never dropped.** `run` prints
  the whole catalogue with a verdict against each: a run that quietly skipped half
  its slices produced a report that looked complete to the only person who could
  tell that it is not.

- **An identifier that cannot be an application registration is refused before
  the network**, instead of starting PowerShell, opening a browser and being
  diagnosed by Microsoft in a window outside the terminal.

- **`spfx` is classified at what it establishes.** Both catalog scopes were
  observed and no solution in either was behind its version, so the branch that
  reports a finding has never been produced by a real catalog. It is
  `negative-only`, not `full`. **This is a downward correction of a published
  claim**, and it is the one number in this release that got smaller.

- **A `--rules` path that is not there says so**, instead of reporting that the
  rules do not validate. **Every `--help` names the manual.** **This engine says
  what it says on a console that is not UTF-8.**

### Contract version change

Every version below is recorded in `data/published-contracts.json` with the
digest it was published under, and a test reads it.

| Contract | Was | Is | Why |
| --- | --- | --- | --- |
| `evidence` | `3.0.0` | `3.1.0` | `tenant.how` and identity fields; additive |
| `collection` | `1.0.0` | `2.0.0` | a required `identity.method` an earlier document lacks |
| `comparison` | `3.0.0` | `3.1.0` | references moved to an optional addition |
| `connection` | `1.0.0` | `1.1.0` | `reason` and `authorization`, both optional |
| `assessment` | `4.0.0` | `4.1.0` | cascade from `evidence` |
| `run` | `4.0.0` | `4.1.0` | cascade |
| `run-set` | `4.0.0` | `4.1.0` | cascade |
| `capability-manifest` | — | `1.1.0` | new in this release, then a fifth live state |
| `migration-read` | — | `1.0.0` | new in this release |
| `migration-verification` | — | `1.0.0` | new in this release |

- **Three published contracts had changed shape without changing name**, and
  nothing in the repository could say so. `collection/1.0.0`, `comparison/3.0.0`
  and `evidence/3.0.0` were edited after `1.0.0b6` published them: a consumer that
  had declared support for any of the three would have carried on declaring it
  while reading a different shape. The versions the cascade did move were moved by
  hand, and by hand is how these were missed.

- **A version's digest is recorded when the version is.** The generated manifest
  could not do this job: it is rewritten from whatever is on disk, so it agrees
  with a silent edit by construction. The ledger is written by hand, disagrees,
  and found all three.

- **`evidence/3.1.0` says how provenance knows which tenant a document is
  about**: `tenant.how` is `requested`, `public-discovery` or `observed`.
  `tenant.id` is null throughout this engine, so the host carries the identity,
  and that host is the address the caller asked for, verified by nothing. Every
  document written today says `requested`.

- **`capability-manifest/1.1.0` adds a fifth live-validation state, `partial`.**
  Four states could not describe a slice that reads several independent areas and
  has observed some of them: `full` claims a path that was not taken, and
  `provider-only` says this slice's own path read nothing, which is false when it
  read two of its four. There was no honest value, so licensing would have shipped
  carrying a wrong one — and a wrong state is worse than a coarse one, because
  everything downstream derives from it rather than from the sentence beside it.

### Known limitation

- **Licensing produces no conclusion about changing an assignment**, and will
  not until dependency evidence exists. That conclusion needs evidence of use
  **and** of dependency; this reads the first at best. `dependency_evidence` is
  recorded as missing by construction so that a usage figure cannot be read as an
  answer.

- **There is no total number of licences.** `units_purchased` existed and was
  removed rather than corrected: it summed `prepaidUnits.enabled` across SKUs and
  returned a seven-figure number on a tenant with a few dozen assigned seats —
  arithmetically correct and meaningless, because the count means something
  different on a paid seat SKU and on a free or effectively unlimited one. It is
  not replaced by a better total. SKUs are published one row each.

- **No rule reads licensing, customization, agents or conditional-access.** Four
  of thirteen slices feed no rule, and each one names its consumer instead.
  Microsoft documents the customization controls as reaching less than their names
  suggest and in two cases prints the limit itself; it publishes no normative
  conclusion about which Conditional Access policies an organisation should have.
  A threshold invented here would make a pass mean nothing. Widen what can be
  observed first; decide what may be concluded after.

- **The fact vocabulary cannot separate *unread* from *unset*.** A fact's state
  is one of `observed`, `missing`, `not-supported`, `permission-denied`, `partial`
  and `invalid`, and none of them means *this run did not make that read*. It is
  carried as `missing` with a sentence saying so. For a product whose claim is
  that an unknown is never a pass, that is worth deciding rather than working
  around, and the decision is queued rather than guessed.

- **This engine writes nothing to a tenant and acquires no credential.** It
  names the command that produces an application registration; it registers
  nothing itself.

### Not established

- **The licensing usage report has never been requested from a real tenant**,
  and dependency evidence is collected by nothing. Licensing is published as
  `partial` for exactly that reason: assignment and report identifiability were
  observed against a real directory on 2026-08-21, and the other two areas have
  never run.

- **`customization` has never run against a tenant.** It is published as
  `none`: offline tests only, which is to say the collector behaves as somebody
  believed the API behaves.

- **The `conditional-access` slice has not itself been run against a tenant.**
  The transport underneath it has, against the whole answer matrix; the slice's
  own path has not. It is published as `provider-only`.

- **`spfx` has never produced a finding from a real catalog.** See the downward
  correction above.

- **`tenant.how: observed` is claimed by nothing**, and will not be until a
  collection path for the directory identity is proven on a tenant.

- **Every state above is published in the capability manifest and in
  `docs/COLLECTOR-LIVE-MATRIX.md`**, per slice, so that none of this has to be
  remembered.

## 1.0.0b6

`connect --format json` becomes a contract, having been argued not to be.

**The reasoning was wrong and it is worth saying how.** The first version
published this shape and called it deliberately unversioned, because a session
ends when the process does and so has nothing to persist. That answers the
wrong question: persistence is not the test, **dependence** is. A consumer
already parses it to decide whether a collection may start, and a shape
somebody depends on is a contract whether or not it is called one — the only
difference being whether it can change without anybody noticing.

- **A new contract**, `connection/1.0.0`, generated model and all. It describes
  an attempt rather than a resource, which is why it is a contract of its own
  and not a corner of the evidence: no rule reads it, no assessment carries it,
  and it produces no finding.
- **`address` and `session` are separate blocks**, and `observed_tenant_id` may
  never be filled from `resolved_tenant_id`. The schema says so where somebody
  editing it will read it.
- **`address.host` is null when nothing was resolved**, found by validating the
  document for an attempt where the collector never ran: echoing back the
  address that was asked for would have put a request where a reader expects a
  result. What was asked stays in `requested`.

Not in this release, and a decision of its own: whether evidence provenance
gains the resolved id at all. It would need a field with its own name and its
own semantics, and a new version of the evidence contract — never
`observed_tenant_id`, which means what a collection saw.

## 1.0.0b5

Two commands' worth of honesty about reaching a tenant, and the release gate
that should have existed before `1.0.0b4` went out.

### `connect`: the other half of `doctor`

**Nothing answered whether you can reach the tenant.** `doctor` reports whether
this installation is sound. Whether the application registration in front of
you can reach the tenant in front of you, and as whom, was found out several
minutes into a collection, from a failure that looked like a tenant problem
rather than a consent problem.

- `m365-governance connect --client-id X --tenant-url Y` opens a read-only
  session, streams what the collector prints — including the device code
  somebody has to read off the screen — and reports what was established.
  Four words rather than a boolean: `established`, `refused`, `unreachable`,
  `cancelled`. A tenant that answered and would not have us is a different
  sentence from one that never answered, and collapsing them sends a person to
  check their network when the answer was consent.
- **Two questions, and one field would answer neither.** `connect` reports
  *address resolution* and *the authenticated session* as separate blocks:

  ```text
  Address resolution
    <host>  owned by  <directory id>
    Public discovery, and no session was involved.

  Authenticated session
    identity   delegated
    observed   not established
  ```

  Which directory owns an address is answerable by anybody, from public OpenID
  discovery, without a token — measured against a real tenant with an empty
  MSAL cache, and separately against the endpoint itself with no authorization
  header. Which directory a session operated in is answerable only by the
  session. **A GUID the whole world can obtain without reaching a tenant is not
  evidence that a collection looked at it**, so `resolved_tenant_id` and
  `observed_tenant_id` are separate and the second is null.

  The address resolves *before* the sign-in and is reported whatever the
  sign-in does: a tenant that refuses us still has an address, and somebody
  diagnosing a consent problem is helped by knowing which directory they were
  actually pointed at.

- **It never says which organisation answered.** A host is an endpoint; the
  identity is the directory id, and no collection path for it is proven on a
  tenant. So a successful sign-in reports the address and
  `identity: not-established`, and says why in the report itself.
- It writes no evidence and produces no document. A connection is not an
  observation about a resource, and it is deliberately not a contract: what it
  reports is the state of a session that ends when the process does.
- A `Connect` mode in the collector, which writes nothing and returns before
  any evidence exists.

**A documented path for the directory identity exists, and we said there was
none.** `Get-PnPTenantId -TenantUrl` is documented as not requiring an active
connection. Recorded in `docs/COLLECTION-PATH-AUDIT.md` as
`needs-tenant-validation` rather than implemented: documentation proves the
cmdlet exists and what it accepts, and only a run proves it returns a value.

**The measured surface was counting comments as calls.** `used()` in
`tools/surface.py` was a regular expression over the collector's source, so the
moment a comment explained why `Get-PnPTenantId` was *not* being called, the
published document said it was. It reads the syntax tree now, which is what the
read-only gate has always done to the same files, and a test freezes it.

### The gate that was missing after the upload

**A successful upload proves the file arrived. It proves nothing about whether
anybody can install and run it.** `release-check.sh` proves the wheel this
repository builds; nothing proved the wheel a stranger downloads, and twice a
version uploaded cleanly and was wrong on arrival — `1.0.0b2` with an install
command that resolved to nothing, `1.0.0b4` with one naming `1.0.0b3`. A
release description is frozen at upload, so neither could be corrected without
spending another version.

- `tools/post-release-check.sh` creates a throwaway environment, installs from
  the **public index**, and refuses unless the program reports the version that
  was released, `doctor` is happy, packaged evidence evaluates and decides
  something, the commands a reader is given all run, and the contract bundle is
  in the wheel. Then it destroys the environment.
- `publish.yml` runs it after every publish, waiting for the index to serve the
  version rather than assuming it does.
- `docs/RELEASING.md`: **until it passes, the version is uploaded rather than
  released**, and the site follows in the same slice.
- **`pip install` is the wrong command for this, and on many machines it is not
  even possible.** A modern Python refuses to install an application into the
  system environment (`externally-managed-environment`, PEP 668), which
  Homebrew's Python, Debian's and Ubuntu's all enforce. The README now gives
  `pipx`, with a virtual environment as the alternative.
- The README's status line was stale in every number it carried: it claimed 18
  rules, a ten-mode collector, 8 profiles, ten commands and 350 tests at 91 per
  cent. Measured: 20, twelve, 9, 13, and 802 tests at 90 per cent.

## 1.0.0b4

A collection now reports what it is doing while it does it, and says what it
managed to do when it stops. Both were missing, and the second one is a new
contract.

**A collection had no account of itself.** The only thing a caller could read
was a process exit code, and a run that reached two hundred of three hundred
sites and then lost its connection had the same value as one that never
authenticated. The first produced evidence worth two hundred sites. That
collapse is made nowhere else here: coverage keeps `requested` and `completed`
apart, and a rule answers `unknown` rather than failing when the gap could
change its answer.

- **A new contract**, `collection/1.0.0`. A `collection-manifest.json` is
  written beside the evidence, on every path including the failure that
  produced no evidence at all. It carries the state, the facts behind it, what
  was asked for, what was observed, the identity that looked, the coverage as a
  union of the artefacts' own, every artefact with a digest over its bytes, and
  a digest over itself. Full contract in
  [docs/COLLECTION-MANIFEST.md](docs/COLLECTION-MANIFEST.md).
- **Four states** where there was a boolean: `completed`, `partial`, `failed`,
  `cancelled`. `partial` is not a failure and `collect` exits `0` for it.
  `cancelled` is set by the caller and never inferred from an exit code.
- **The collector's output streams.** It was buffered until the process exited,
  so `collect sites` against a large tenant printed nothing for however long it
  took and then printed everything — including the line saying how many sites
  the identity had enumerated.
- **`evaluate` states the bound before the results**, on stderr, where a
  manifest exists. Where none exists it says nothing: evidence collected before
  this contract, or exported from elsewhere, carries no account of its own
  completeness, and inventing one would report a gap that was never measured as
  an absence of gaps.
- **A manifest is not evidence.** `collect` does not count one as a document it
  wrote, and `evaluate` does not hand one to the evaluator.
- **Two collections into one directory no longer destroy each other's record.**
  The second carries its own short identity in the filename. Overwriting would
  have removed the only statement that the first was partial.
- The canonical form moved to `m365_governance/canonical.py`. Two documents now
  publish a digest a recipient recomputes, and a second copy of those four
  lines would be a second definition of the canonical form.
- **The model generator refuses two records with one name.** Found by adding
  this contract: it emitted three records called `Versions` and two called
  `Coverage` into one namespace, all different shapes. Every file was
  individually correct, the manifest was consistent, and the bundle would not
  have compiled — which nothing here would have said, because nothing here
  compiles it.

Two defects the contract itself exposed, both found by reading a manifest it
had just written rather than by reading the code:

- **A clean exit that wrote nothing reported `completed`.** The state is now
  `failed` whenever there is no artefact, whatever the exit code: no usable
  artefact is what the contract calls `failed`, and telling a consumer that
  everything was read by a collection that wrote nothing down is the
  rounding-up these states exist to stop, made by the type meant to stop it.
- **A dry run had a state.** It reaches no tenant and gave a collector nothing
  to do, so asking for one now refuses instead of answering `completed` about
  an estate nobody looked at.
- The reason an area was not read reached the manifest and stdout as a Python
  dict repr, braces and quotes included, where a sentence belonged.

What is **not** in this release: an assessment still does not record which
collection produced its evidence or in what state that collection ended. That
costs an assessment contract version and is the next step.

## 1.0.0b3

A correctness fix, not a cosmetic one. `1.0.0b2` reported the wrong version of
itself, and signed its assessments with it.

`__version__` was a literal in `m365_governance/__init__.py`, beside the one in
`pyproject.toml`. Bumping the packaging version to `1.0.0b2` left the literal at
`1.0.0b1`, so the wheel was named for one version and the program answered with
another. Nothing caught it: the publish workflow compares the built filename to
the release tag, and those agreed. The drift was between the filename and the
running program.

The naming half is cosmetic. The other half is not. That value travels into
every assessment as `engine_version`, so an assessment produced by `1.0.0b2`
states that `1.0.0b1` decided it. In an engine whose whole claim is that a
conclusion can be traced back to what produced it, a version that lies is not a
typo. The generated contract manifest carried the same stale number, so a
consumer comparing contract versions across the two releases saw no change.

- `__version__` is now read from the installed distribution metadata, which
  comes from `pyproject.toml`. One source, and no way to bump one without the
  other.
- `tests/test_version.py` compares the packaging version with what the program
  reports, both by import and through `--version` as a user would run it, and
  refuses to let the not-installed fallback pass as a real version.
- The contract manifest is regenerated.

`1.0.0b2` stays in the history as a release with a known defect. It is not
withdrawn and its number is not reused.

## 1.0.0b2

The first release whose project page is right. Nothing in the engine changed.

`1.0.0b1` shipped a README whose banner used a relative path and whose install
command omitted the pre-release pin. GitHub resolves a relative path against
the repository; PyPI has none, so the project page opened with a broken image.
And `pip install m365-governance-as-code` resolves to nothing while the only
version is a pre-release, which is the first command anybody was given.

A release description on PyPI is frozen at upload, so correcting the file could
not correct the page. This version is what publishes the corrected one.

- README: absolute URL for the banner, `==` on both install commands.
- README: `doctor` no longer claimed to print where the packaged fixtures live,
  because it does not. The command that resolves the directory is given instead.
- README: badges for the published version, the Python versions CI runs against,
  the licence and the state of `main`, each with a line saying what it reports
  and what it does not.
- `docs/RELEASING.md`: the publishing procedure, including the two things that
  cannot be fixed after an upload.

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
