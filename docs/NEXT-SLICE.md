# Continuous execution queue — Microsoft 365 governance surfaces

**Programme state:** `ACCEPTED_FOR_CONTINUOUS_EXECUTION`

**Owner decision:** 2026-08-17

**Execution base:** `main@7d1ded4` — the installation slice merged as PR #24,
so the finding it closed is removed from this queue rather than kept as history.

**Integration rule:** #24 is merged. The Executor does not merge; the owner decided
this one, and a branch carrying older non-conforming commit messages is squashed with
an explicit English subject and body so that nothing non-conforming reaches `main`.

This file is the canonical Engine queue. Every numbered slice in this file is already
accepted for execution. The Executor starts at the first slice that is not `QA_READY`
and continues in order without conversation, scratchpads, roadmap ratification or a
new owner approval. Completed work is removed from the active queue rather than kept
as queue history; its PR, commits and release evidence remain the historical record.

**WHERE THE PRODUCT IS, 2026-08-21.** The order below is decided in advance by charter
`D59` and is not rewritten by whatever the last inspection found. A slice that does not
belong to a named capability does not start, and a finding outside the roadmap is
recorded rather than promoted into it.

### NOW

**`LICENSE-OPTIMIZATION-001`** — *what is assigned, what service plans it contains, and
what usage evidence is observable for each.*
**owner:** owner · **evidence needed:** the Graph reads against a real directory ·
**done when:** a canonical bundle from a live tenant opens in a consumer and shows
assignment, usage and dependency as three separate states · **blocker:** a tenant. The
fixture-fed half is built and gated; nothing further is provable without one.

### NEXT

**`BRAND-CENTER-001`** — *what organisational assets are published, by whom, and through
which distribution boundary.* **owner:** owner · **evidence needed:** site authority,
organisation asset libraries, the CDN publication path · **done when:** the distinction
between an administration boundary and a distribution boundary is evidence rather than
prose · **blocker:** none recorded.

**`BRAND-CENTER-001` is the next genuinely open capability.** `AGENT-GOVERNANCE-001` is
not: its first vertical is established. The collector carries `population`,
`acquisition_method` and `populations_not_observed`, two fixtures exercise a populated and
an empty population, the canonical bundle opens in a consumer, and the boundary is stated
in the evidence rather than in prose. What remains there is a second slice, listed under
LATER: creator authority and the publication surfaces beyond `.agent` files.

### LATER

`AGENT-GOVERNANCE-002` — creator authority and the publication surfaces a `.agent` file
read cannot reach. **evidence needed:** the administrative surface that lists agents built
outside SharePoint · **done when:** the second population is stated the way the first one
is.

`ENGINE-FACT-STATE-NOBODY-LOOKED-001`, `ENGINE-CONTRACT-LEDGER-002`,
`MIGRATION-VERIFY-001`, and the residual-defect list under `FIRST-RUN-006`. Real work,
none of it blocking a capability in NOW or NEXT.

### FROZEN

`FIRST-RUN` functional expansion, by the owner decision below. `PAGE EXECUTION`
(`ENGINE-PAGE-CONTROLS-001`) is closed as an observation capability and is deliberately
not extended: rules stay at zero until there is a sentence somebody can defend.

### NOT ESTABLISHED — needs a tenant, a licence or an identity

`ENGINE-CLEAN-MACHINE-001` and `002`, `FIRST-RUN-002`'s live path,
`CUSTOM-SCRIPT-SEMANTICS-001`'s runtime half, and the live half of everything in NOW.
These are not blocked work; they are work whose evidence cannot be obtained from this
machine.

### STANDING RULES, not slices

`ENGINE-SEARCH-IS-NOT-ENUMERATION-001`. It never completes and never leaves.

The cards are executable contracts combined with the common contract below; they are not
ideas, options or a backlog requiring refinement by the Executor.

## FIRST-RUN — the journey has an owner, and functional expansion is frozen until it works

**Owner decision, 2026-08-20.** An independent product audit found that this engine is
good and that its product begins too late: quality is reachable only after a new user
has crossed, unaided, the most ordinary part of any Microsoft 365 tool — install, obtain
an identity, connect, prove access, run, receive a result. The audit's central finding is
not that a `run` command is missing. It is that **the first-run journey had no owner**,
so the Engine, the site and the desktop product each told a different version of the
truth and no gate could fail.

Ownership is now recorded: `docs/FIRST-RUN-CONTRACT.md`, and in `AGENTS.md`.

**The freeze.** No new collector, workload, rule, output format or report capability
starts until the slices in this section are `SHIPPED`. That includes Exchange, Teams,
further Entra work, SARIF, additional rules and report sophistication. `IDENTITY-CA-001`,
`IDENTITY-APPS-001` and `MIGRATION-VERIFY-001` keep their contracts, in their present
order, and resume after this section — they do not resume before it.

**The version position.** No further product is added on top of `1.0.0b6` while the
published documentation describes commands that version does not contain. The exit of
this section is a coherent beta from which the site derives, proven by
`tools/post-release-check.sh`.

**Position, 2026-08-20, after 001 to 006.** In the vocabulary of charter `D46`:

```text
FIRST-RUN 001-006   CONTRACT-PROVEN
AUDIT               CONTRACT-PROVEN   the four residual defects are closed
LIVE-OBSERVED       not established   no run has been performed against a tenant.
                                      Costs a credential. Highest risk reduction
                                      per unit of effort
SHIPPED             not established   the public index is behind this branch.
                                      Blocked by an owner's publication decision
MARKET              not established   FIRST-PRODUCT.md names no product.
                                      Decided outside this repository
```

**They are independent questions and they are not equally cheap to get wrong.** Observing
needs a credential and no release: the wheel this branch already builds is enough.
Publishing is the step that cannot be taken back — after it, a defect is no longer an
internal finding, and the person who meets it met it first. Publishing before observing
therefore delivers a journey nobody has run, and the four defects found on 2026-08-20
were found by running rather than by testing, with a green gate and ninety per cent
coverage standing over every one of them. The reverse dependency does not exist.

`FIRST-RUN` being `CONTRACT-PROVEN` and the audit being closed are different claims, and
only the first is true. The audit line is carried here rather than in a paragraph
underneath, because a state somebody has to read prose to discover is a state that gets
reported as absent.

Four separate closures over things that already exist, and none of them needs new
architecture. Three of the four are not engineering: a release needs an owner's
authorization, an observation needs a credential, and a market needs interviews.

**The four residual defects are closed, 2026-08-20.** One was worse than the audit
recorded. `Resource: <unknown>` was not a fixture without a display name: the line read
`resource["id"]`, a key no evidence document has ever carried, because identity is
structured and was deliberately never collapsed into a parsed string — so **every
markdown report this engine has produced printed `<unknown>`**, on the second line,
beside a title that had the name in it all along. A `--rules` path that is not there no
longer arrives as "the rules do not validate", which sent a reader to inspect rules that
were fine. Every `--help`, from the one place parsers are built, names the manual. And
`doctor` gives a remedy for a missing `pwsh` as it already did for a missing
PnP.PowerShell.

**The recurring defect, named so that the next executor looks for it.** Four instances in
one day, and one shape: **a step producing a verdict from a source that could not have
produced it.** `unknown` read as an answer; discovery failing and the sign-in proceeding;
a requested address standing in as the tenant an assessment is about; and seventy-one
tests skipping while the suite stayed green. Charter `D49` states the rule. What it does
not do is find the next one — and every one of these four was found by running the thing,
never by reading it.

**The test that replaces the old one.** The measure of readiness stops being coverage of
rules by evidence path. It becomes: *on a clean machine, a person who knows Microsoft 365
but has never seen this product can install it, obtain and configure the identity, prove
they have access, and open a first report — without reading code, editing JSON, or
guessing internal architecture.*

### FIRST-RUN-001 — nothing interactive begins on an input that could be refused locally

**authority:** repository · **next action:** none: `CONTRACT-PROVEN`, shipped by the release

**State:** the path half is closed. `evaluate`, `assess`, `stats`, `report`, `verify` and
`diff` refuse a path that is not there with exit `2` and one sentence, and the exit-code
contract they are measured against is published on the site.

**What is missing.** `--client-id` is accepted in any shape. A value that is not a GUID
starts PowerShell, opens a browser and fails in the directory, so the product's own worst
error is diagnosed by Microsoft, in a window, outside the terminal. Audited on
2026-08-20 against a live tenant: `--client-id not-a-guid` reached `AADSTS700016`.

**Done when:** an identifier that cannot be an application registration is refused before
a process is started, with exit `2`; and the `AADSTS` codes a caller can act on are
carried as a reason rather than as the collector's last three lines of output. The
engine's own rule already says the cheapest place to stop is before the network — it is
enforced today for authentication modes and for nothing else.

### FIRST-RUN-002 — `connect` means "this identity can work here"

**authority:** observation · **next action:** the owner's hour: application identity end to end

**What is wrong.** `connect` accepts `--certificate-path`, `--tenant-id` and
`--certificate-password-env`, validates them, and then does not pass them:
`connecting.py` does not contain the word. `collect` passes them, and the PowerShell
collector supports application-only in every mode including `Connect`. The one command
whose purpose is to prove an application registration can reach a tenant cannot prove it
for the identity an unattended run uses.

**Second half.** Authentication and authorization are two answers. A session opens with
zero permissions granted, and a product that stops after the first has reported the
second.

**Done when:** application-only works end to end through `connect`; the result
distinguishes "signed in" from "can read what the rules need"; and the failure carries an
enumerated reason beside `reach`, so that no consumer — the desktop product first among
them — has to regular-express English out of PnP.PowerShell.

**Contract decision, taken:** `connection/1.1.0`. `reason` and `authorization` are
optional in the schema so that a document written before the change still validates, and
every producer at 1.1.0 emits both. Optionality is compatibility with the past, never
licence for a producer to omit a field and leave every consumer carrying a fallback — a
consumer tells a legacy document by the version it declares. `connection/1.0.0` is
archived rather than deleted.

**State, 2026-08-20:** `CONTRACT-PROVEN`. Not `LIVE-OBSERVED` for its main path, and
the four states are charter decision `D46`: a green gate proves the contract and nothing
above it.

Application-only reaches the collector, the session reports the identity it actually
holds, authorization is asked and answered separately from authentication, and every
failure carries `reason`. Proven from the installed wheel against a directory that does
not exist: `reason: directory-not-found`, exit `1`, no traceback, no browser.

Two defects were found by that live run and not by any test, which is the argument for
running it: the collector's own protocol lines and another product's terminal colour
were printed to the reader, and `because` carried a trace id and a correlation id
instead of the sentence that named the problem. Both are fixed and both are now tests.

**The one action that unblocks the rest:** an application registration in a tenant, with
a certificate uploaded to it and `Sites.Read.All` consented. Without it, no run can
demonstrate `reach: established` with `identity_kind: application`, and
`authorization: established` has never been observed — only its `denied` and
`not-attempted` branches. The slice does not reach `LIVE-OBSERVED` for application identity until it has been, and
does not reach `PRODUCT-PROVEN` until somebody completes the published journey through
the surface a user is given.

### FIRST-RUN-003 — a configured target, and no secrets in it

**authority:** repository · **next action:** none: `CONTRACT-PROVEN`

**What is wrong.** There is no project file and no sanctioned defaults. Ten slices are ten
commands, each retyping `--client-id` and an address; the audit counted the same two
arguments written eleven times. The refusal to read PnP's ambient client id is correct —
evidence must be able to name the identity that observed it — but it was never replaced.

**Done when:** a project file carries client id, tenant and site targets, authentication
mode and profile defaults; secrets are not in it and there is no option that would put
them there; and the resolved identity is recorded in the evidence provenance, which is
what the original objection actually asked for.

**State, 2026-08-20:** `CONTRACT-PROVEN`. A project file carries the target and the
identity, the command line always wins over it, a key naming a credential is refused
rather than ignored, and the file that was read is named on every run. Not
`LIVE-OBSERVED`: it has not been exercised against a tenant.

**Found while proving it, and it is the sharpest defect of the day.** `connect` resolves
which directory owns an address, by public discovery, before signing in. Where nothing
owned the address it signed in anyway — and an interactive sign-in with no directory to
go to lands in whichever one the browser is already signed into, then reports what it
found there as an answer about the address that was typed. Observed twice on 2026-08-20
against a live tenant, the second time from a host that does not exist: the browser
opened against an unrelated directory and returned `AADSTS700016`, a true sentence about
the wrong tenant. **The engine had the evidence and used it for nothing**, which is the
failure this product exists to make impossible. It is refused now, before the sign-in,
and a certificate still proceeds because `-Tenant` names the directory.

`connect` also gained `--dry-run`. `collect` has had one since it existed; the command
somebody runs while working out how any of this fits together had no way to be tried, so
the only way to see what it would do was to let it do it.

### ENGINE-PAGE-CONTROLS-001 — the customization surface is collected, and reads nothing into it — `CLOSED`

**authority:** repository for the collection; owner for any rule built on it ·
**next action:** none. Closed 2026-08-21 as an observation capability, and not to be
expanded: a rule needs a sentence somebody can defend, and until there is one, zero rules
is the correct state rather than a gap

**Built 2026-08-21.** `Customization.psm1` and the `Customization` slice collect, per
site: the custom script setting where a tenant-scoped read was made, whether the
identity holds `AddAndCustomizePages`, whether the Site Pages web feature
`B6917CB1-93A0-4B97-A84D-7CF49975D4EC` is present, whether the Site Pages library is
readable, and whether it carries unique permissions. Three fixtures exercise the three
situations that must not be conflated: every surface read, the tenant read nobody made,
and the feature absent with the library refused.

**The evidence answers one question**: *what customization and page-execution control
surfaces are observable on this site?* It does not answer *is this site safe* and it does
not answer *can no interactive content run here*.

**Four surfaces, and this collects one.** Configuration is here. Content is the Site
Pages library, whose count `Modernity.psm1` already owns and which is not repeated.
The administrative execution path is SPFx and the app catalog, which `Spfx.psm1` owns.
Browser runtime policy -- CSP and strict file handling -- is read by nothing. They are
different questions and mixing them is how a reader concludes one from another.

**RULES REMAIN ZERO, DELIBERATELY.** A rule reading any of these as a pass or a fail
would be the conclusion the published article
`/knowledge/sharepoint/what-custom-script-disabled-establishes/` exists to refuse.
Microsoft documents each control as reaching less than its name suggests and in two
cases prints the limit: nine blocked extensions with `.html` absent, and page-creation
prevention that *hides* entry points while *users can still add pages from other modern
pages*. First widen what can be observed; only then decide what may be concluded.

### ENGINE-FACT-STATE-NOBODY-LOOKED-001 — the vocabulary cannot say that nobody asked

**authority:** owner · **next action:** decide whether the collection state vocabulary
gains a term, or whether the detail line is the answer

Building the slice above found a gap. A fact's `state` is one of `observed`, `missing`,
`not-supported`, `permission-denied`, `partial`, `invalid`. **None of them means *this
run did not make that read*.** `DenyAddAndCustomizePages` is returned by a tenant-scoped
read; a site-scoped run cannot make it, and the honest report is neither *missing* nor
*permission-denied*.

It is carried today as `missing` with a detail saying *not read is not the same as not
set*, which works and depends on a sentence rather than on a field. For a product whose
whole claim is that an unknown must never be reported as a pass, **a vocabulary that
cannot distinguish unread from unset is worth the owner's attention**, and the decision
is a contract change rather than an implementation.

### ENGINE-SEARCH-IS-NOT-ENUMERATION-001 — a query result is a population, never an existence claim

**State:** `STANDING RULE`, owner, 2026-08-21. **authority:** owner ·
**next action:** applies to any collector that queries rather than enumerates

> **A search that returned nothing has not established that the resource does not
> exist. It has established what that query matched.**

Established twice by observation on 2026-08-21: a tenant search for assets returned
nothing while the assets existed, and a Graph-backed search for an agent by its exact
name returned only unrelated files while the agent existed. The generalisation the
second one forces is worth stating on its own: **an inventory surface defines a
population; it does not define existence outside that population.**

No collector in this engine currently queries -- `Agents.psm1` and every other module
**The day one does, the distinction has to survive into the evidence**, not
live in a comment: *this query returned zero* and *this enumerated population is empty*
are different facts, and a consumer reading the second where the first happened has been
handed a false absence by the acquisition method itself. It is a property of how the
evidence was acquired and belongs beside it. A test for false absence comes with the
first such collector.

### LICENSE-OPTIMIZATION-001 — what is assigned, and whether its use can be observed at all — `FIRST SLICE BUILT`

**authority:** owner · **next action:** owner's hour to wire the Graph reads against a
real tenant; nothing else can be proved without one

**The first question, and there are no rules in it.** *What licenses are assigned, what
service plans do they contain, and what usage evidence is actually observable for each
one?* Built 2026-08-21 as `Licensing.psm1`, three declared fixtures, a canonical bundle,
and it was opened in a consumer.

**ONE MICROSOFT FACT DECIDES WHETHER THIS CAPABILITY IS POSSIBLE, AND IT IS COLLECTED
FIRST.** *By default, all reports hide user information such as usernames, display names,
groups, and sites*, and *this setting also applies to the Microsoft 365 usage reports in
Microsoft Graph*. In a default tenant the usage evidence **cannot be joined to a user at
all** -- not partially, not approximately. `report_identifiability` is therefore the first
fact, because every figure after it is conditional on it, and turning concealment off is
itself *a logged event in the Microsoft Purview portal audit log*.

**Three more ways to be wrong, each now a fact rather than a footnote.** The reports cover
*the last 7, 30, 90, and 180 days*, so an absence is an absence within a window. They
*typically become available within 24 to 72 hours*, so the newest days are not there. And
*when you delete a user account, Microsoft deletes that user's usage data within 30 days*,
which removes the evidence exactly where a conclusion would otherwise be strongest.

**And a join Microsoft says does not exist:** *you can't generate a report where you enter
a user's account and then get a list of which services they're using and how much.* The
per-user cross-service view is assembled from per-service reports or it is not assembled,
so the evidence records which reports were actually read instead of implying a whole
picture.

**THE RULE THIS CAPABILITY LIVES OR DIES BY, unchanged:** nothing may be concluded about
changing an assignment without evidence of both use and dependency. The question is not
whether a user can cost less; it is what capability would disappear. `dependency_evidence`
is recorded as `missing` by construction, because this collector reads none, and that
absence is a fact so a consumer cannot read a usage figure as an answer.

**What a consumer shows today**, opened against the canonical bundle: *No governance
conclusion was produced for this resource. Evidence was collected, but no rule was
evaluated against it. 2 areas were not observed at all*, with `assignment` complete and
`usage` and `dependency` unavailable in their own words. Honest, and already useful.

**What is not built and needs a tenant:** the Graph reads themselves. `Get-LicensingFacts`
takes objects a caller supplies, so it is provable against fixtures; wiring
`Get-MgSubscribedSku`, the per-user assignments, `adminReportSettings` and the usage
reports into a collector entry point is an hour against a real directory and cannot be
proved without one.

### AGENT-GOVERNANCE-001 — a different population, a different authority — `FIRST VERTICAL ESTABLISHED`

**authority:** owner · **next action:** none for the first vertical. The second is
`AGENT-GOVERNANCE-002` under LATER

Shares the methodology of the slice above and none of its domain. Who may create an
agent, what knowledge sources it may use, which modes are included and which are metered,
what population each API or cmdlet actually covers, and the difference between *an agent
exists* and *an agent appears in this inventory surface*.

The strong finding is already recorded on the public side: `Get-PnPCopilotAgent` reads
`.agent` files in SharePoint, an agent built in Agent Builder is not one of them, and a
search for one by name returned unrelated files. **An inventory surface defines a
population. It does not define existence outside that population.**

Not opened now. Different collectors, different limitations, different authority, and
methodology fitting is not a reason to merge two domains into one expansion.

### ENGINE-CONTRACT-LEDGER-002 — the ledger depends on somebody remembering — `RECORDED, NOT OPEN`

**authority:** owner · **next action:** none: recorded so the ceremony is written down, not queued. Opening it needs the owner to decide what establishes that a version is new rather than changed

`data/published-contracts.json` records the digest of every contract version when
that version is published, and `tests/test_registry.py` refuses a version whose
bytes have moved. It found three contracts that had been edited under an identity
already published, which is the failure it exists to catch, and it will keep
catching them.

**What it does not do is add the line.** A new version arrives with a new digest,
and the person introducing it writes that line by hand in the same change. If they
forget, the test says the version is not in the ledger and the fix is to add it —
which is the correct instruction and also exactly what somebody would do to silence
a real mutation. The gate is sound in the direction that matters and depends on a
human ceremony in the other.

**Not open, and deliberately.** Silent mutation is prevented today, which was the
risk. Automating the ceremony means deciding what evidence establishes that a
version is genuinely new rather than genuinely changed, and the honest answer is
the release history, not the tree. That is a slice with an owner decision in it,
and it does not block anything currently queued.

### ENGINE-CLEAN-MACHINE-001 — run the journey where nothing is installed

**authority:** repository · **next action:** re-run at the next release candidate

**Opened 2026-08-20.** Every defect found that day was found by running, none by reading,
with a green gate standing over all of them. **The journey has never been run on a machine
that is not this one**, and this one has a project checkout, a warm PowerShell, a PnP
module, a configured shell and — as it turned out — a stale release on `PATH` that
shadowed the engine under test for a whole session.

**The slice.** Build the wheel, install it into a fresh environment with a fresh `HOME`,
and execute the published journey as far as it goes without a tenant: `doctor`, `setup`,
`connect --dry-run`, `run --dry-run`, and every refusal. **Record what a first-time reader
meets**, not what the tests assert.

It is `D46`'s `PRODUCT-PROVEN` minus the tenant, and it is the cheapest evidence left that
nobody has collected.

**It repeats at every release candidate.** Rule 5 of the charter's continuation procedure
is a routine and not a virtue: an environment nobody has used is where the defects that
survive a green gate live, and one clean run does not immunise the next release.

**Run 2026-08-20: fresh `HOME`, bare `PATH`, no PowerShell, no PnP, no checkout.** The
journey holds. `doctor` names both absences and gives the command for the one it can;
`setup` prints the registration command and writes the project file; `setup` again, with
an id, hands over to `connect` and `run`; every refusal is one sentence and exit `2`.

**And it found one defect that no test could have.** `run --dry-run` printed
`Plan: 2 of 11 collections` and exited `0` on a machine with no PowerShell — and a dry run
is precisely what somebody uses to find out whether they are ready. The Graph slice
already reported its missing token; the ten that need an interpreter said nothing about
it, while `doctor` and the preflight both knew. The plan asks now, and the same machine
reports `Plan: 0 of 11` with a reason against every line and exit `2`.

**State:** `LIVE-OBSERVED` for everything that does not need a tenant. The three claims
that do — `authorization: established`, `identity_kind: application`, `tenant.how:
observed` — are unchanged and remain the owner's hour.

### ENGINE-QUEUE-CLAIM-001 — `nothing remains` becomes a claim a gate can refuse

**Opened 2026-08-20.** Rule 8 of the charter's continuation procedure says a
`nothing remains` claim is established by enumeration and never by fatigue. As prose it
is advice, and advice is what an executor at the end of a long session is least able to
follow — twice on the day it was written.

**The slice.** Every open card in this queue declares two fields:

```text
authority:     repository · observation · owner · interviews
next action:   the one thing that happens when that authority arrives
```

A gate reads them. A card missing either fails the build, and the queue may not be
described as exhausted while one exists. It is `unknown ≠ pass` pointed at the queue: a
card whose authority nobody wrote down is a card nobody can establish is blocked, and the
honest state for it is `not established` rather than `done`.

**Why here and not in the site's queue too.** One implementation, in the repository that
already runs a language gate over its own operational documents. The site adopts it after
it has proven itself here, and not before: a gate copied into two repositories before it
has been exercised in one is two gates to keep true.

**Done, 2026-08-20.** The gate exists, is tested, runs in `release-check.sh`, and every
card carries both fields. Its first run answered the question that had been getting the
wrong answer:

```text
✓ 15 cards, all claimed: 2 observation, 4 owner, 9 repository
  9 of them need no external authority
```

**Nine.** That line is what `no independent executable work remains` was competing with,
and it is now printed by a gate rather than assembled from memory at the end of a long
session.

### ENGINE-SPFX-CLASSIFICATION-001 — a capability declared above its own note

**Closed 2026-08-21.** **authority:** repository · **next action:** none.

`spfx` was `live_validation_state: full` while the `live_note` beside it said *"no
solution in either was behind its catalog version, so the finding branch has not been
produced by a real catalog"*. **The capability declared more than the sentence under it**,
and the site read the classification and published *proved against a real tenant*.

**No new contract value was needed, and one was nearly added.** `negative-only` already
means what happened; its description had narrowed it to *"absent or empty"*, which is a
fact about the surface rather than about which path was exercised. A catalog of ten
solutions with none of them behind its version leaves the finding exactly as unproved as
an empty one does. The description is widened and `spfx` is reclassified — **a correction,
not a version**. Adding a fifth value would have been architecture covering for data, in a
published contract, where it is expensive to undo.

### ENGINE-CLEAN-MACHINE-002 — the journey had met one operating system

**Run 2026-08-21. State:** `LIVE-OBSERVED` on Linux. **authority:** owner, for Windows ·
**next action:** a Windows machine.

**Rule 5 applied where the product risk is largest.** The clean-machine run of the day
before was macOS. The reader of this product is a Microsoft 365 administrator and is
mostly on Windows, and this engine branches on no platform anywhere: `platform.system()`
is reported by `doctor` and decides nothing.

**Linux, in a container, today.** `doctor`, `setup`, the project file, `run --dry-run` and
every refusal behave as they do on macOS. Exit codes hold, the plan reports `0 of 11` with
a reason on every line, and no path, encoding or environment assumption surfaced.

**One defect, and it was the predicted one.** The missing-PowerShell remedy was a URL
where the contract asks for the whole of a diagnosis, and `run` told the reader that
`doctor` gives the command — which was not true on any platform. It is a command now on
macOS and Windows; Linux keeps the link, because the command differs by distribution and
printing one distribution's would be wrong for most readers of it. It is the only place
this engine branches on an operating system, and it selects a sentence.

**Windows was never blocked on a machine.** CI ran `ubuntu-latest` with a Python matrix
and no OS matrix, and `windows-latest` is the same class of free runner. The card
inherited *needs a machine* as if it were the only resolution — rule 1, missed by its own
author on the day it was written. `.github/workflows/ci.yml` now walks the journey on
Windows, Linux and macOS from the built wheel, per push, which also makes rule 5 a routine
rather than a container run once by hand.

**The walk found a second defect.** `run` read a project file from a parent directory and
never said which one: the message was conditional on `--format text`, and `run`'s formats
are `markdown`, `json` and `html`. A file nobody was told about is the ambient
configuration the project file exists instead of. It is on stderr unconditionally now,
which was always the right stream.

**What Windows will settle:** PowerShell 7 beside
Windows PowerShell 5.1 and which one `shutil.which("pwsh")` finds; a PFX and
`--certificate-password-env` under a different credential store; and where
`m365-governance.toml` is looked for when `HOME` is `USERPROFILE`. **It does not settle a
PFX under another credential store**, and saying so keeps a green job from standing for
the whole question.

### ENGINE-RELEASE-TRAIN-001 — make the authorization a non-event

**authority:** repository · **next action:** rehearse `post-release-check.sh` against a local wheel

**Opened 2026-08-20.** The owner's publication decision should cost minutes, not a
session. What can be prepared without taking it: the CHANGELOG closed, the version bump
staged rather than applied, `tools/post-release-check.sh` rehearsed against a locally
built wheel, and the ordered steps from authorization to a proven install from the public
index written down.

**Not authorised by this card:** tagging, publishing, or bumping the version on `main`.

### ENGINE-SHIPPABLE-001 — a release must not recreate the drift in mirror image

**authority:** repository · **next action:** none: the manual is written, behind `unreleased`

**Opened 2026-08-20.** `SHIPPED` was being treated as one decision. It is not. The
published manual documents the old journey: there is no `cli/setup.md` and no
`cli/run.md`. A release carrying `setup`, `connect` and `run` against a manual that
documents none of them produces the same defect that `DOCS-AGAINST-PUBLISHED-001` exists
to catch, pointing the other way — and `docs/FIRST-RUN-CONTRACT.md` obliges the site to
document each step against a published release.

**The slice.** The manual pages for the journey are drafted behind the mechanism
`SITE-UNRELEASED-001` provides: declared as documenting an unreleased tree, checked
against that tree, and not composed into the published artefact. They become publishable
by the release, not by an edit made on the day.

**Not authorised by this card:** publishing, tagging, or touching the version. Those are
the owner's.

**Done when:** the journey has pages, they are proven unpublished, and the day the release
happens the site has nothing left to write.

### ENGINE-OBSERVE-PREP-001 — reduce the cost of the hour that is blocked

**authority:** repository · **next action:** write the runbook, in two dimensions

**Opened 2026-08-20.** `LIVE-OBSERVED` is blocked on one credential and the credential is
the owner's. **The plan for spending it is not blocked.**

**The slice.** A runbook: the exact commands, in order, and which claim each one settles.
Three have never been observed and each needs a different command —

```text
authorization: established    only `denied` and `not-attempted` have been seen
identity_kind: application    end to end through `connect`, not only `collect`
tenant.how: observed          still needs-tenant-validation
```

**`LIVE-OBSERVED` is one tenant AND one operating system, not one tenant.** If the hour
can be spent on Windows it settles two questions instead of one. If it cannot, the runbook
says which half stays unobserved rather than letting a macOS and Linux run stand for the
journey the reader will actually take.

**It records nothing as observed**, and it may not: writing an expected result down is not
observing one. What it removes is a second session spent discovering what the first should
have run.

**Done when:** an hour with a tenant produces every observation this engine currently
lacks, in one pass, without anybody deciding what to type while a credential is live.

### FIRST-RUN-006 — provenance must not name a tenant the session never established — `CONTRACT-PROVEN`

**authority:** observation · **next action:** read the directory from a session, once a tenant exists

**Opened 2026-08-20, from the generalisation of the sign-in defect.** Charter `D49`: an
absence never authorises the step that depends on it.

**What is closed.** The guard now runs for every mode, from the one place that decides
which URL is connected to. It used to live in the script, inside `if ($Mode -eq
'Connect')`, so the single command that writes nothing was protected and the ten that
write evidence were not.

**What is still open, and it is a contract question.** `tenant.id` is null throughout this
engine, and the evidence contract says in as many words that the host therefore carries
the identity. That host is derived from the URL the caller asked for — `Get-TenantHost
-Url $connectUrl` — and never from the session. This engine is fanatical about the same
distinction one contract away: `observed_tenant_id` may never be filled from
`resolved_tenant_id`, "in the one field a reader trusts to mean what was seen". Evidence
does the equivalent by construction, in the field that currently identifies the tenant an
assessment is about.

The guard removes the path that made it dangerous. It does not make the provenance say
what was observed rather than what was asked for.

**Done, 2026-08-20, and deliberately not by inventing the observation.**
`evidence/3.1.0` adds `tenant.how`: `requested` · `public-discovery` · `observed`, the
vocabulary `connection` already uses for the same distinction. Every document this engine
writes says `requested`, which is the truth: the host is the address the caller gave, and
no step in a collection reads the directory the session is operating in.

**Nothing claims `observed` and nothing may until a path is proven on a tenant.**
`Get-PnPTenantId -TenantUrl` is validated but it is public discovery — a lookup anybody
can perform without reaching the tenant — and copying it here is precisely what
`connection` forbids for `observed_tenant_id`. The `-Connection` parameter set would be
an observation and stays `needs-tenant-validation` in `docs/COLLECTION-PATH-AUDIT.md`.
That question is unchanged; what changed is that a reader is no longer left to infer the
answer from a field that looks like a fact.

**The report says it**, because a contract nobody reads is a distinction that does not
exist for the person holding the report.

**Two defects fell out of it.** The tenant block was built inline in the envelope as well
as in `New-TenantIdentity` — the duplication the note above that function warns about,
and the two disagreed the moment one learned to say how the identity was established.
And the run-schema tests shelled out to whatever `m365-governance` was on `PATH`, which
on a developer machine is an installed release: they had been validating a published
build rather than the code under test, and when the contract moved, seventy-one of them
turned into skips without the suite going red once. They run the engine under test now,
and a wholesale skip fails.

### FIRST-RUN-004 — the golden path exists as commands

**authority:** repository · **next action:** none: `CONTRACT-PROVEN`

**Done when:** `setup` prepares and diagnoses an environment, including how to obtain an
application registration; `connect` proves the identity; and `run` takes a configured
target to an assessment and a report. `slice`, evidence directories, `profile` and run
sets stop being prerequisites for a first result and become what they are — the
vocabulary of the report, and material for the reference documentation.

**State, 2026-08-20:** `CONTRACT-PROVEN`.

`setup` runs `doctor`'s own report, then names the one command that produces an
application registration — which nothing in this product named before, the only
instruction anywhere being "register an Entra ID app, or use one your tenant already
has": the hardest step written as an aside. It registers nothing itself. This engine
reads and acquires nothing, and a read-only product that quietly wrote to a directory
during setup would have a write path after all; the gate that proves the collector never
mutates a tenant does not read the CLI, so a test does.

`run` plans from the target, collects what the target can reach, evaluates and reports.
**Every slice appears in the plan with a verdict**, including the ones that will not be
attempted and why: a run that quietly skipped half its slices would produce a report that
looks complete to the only person who could tell that it is not. It is `D49` one layer
further out. A collection that fails does not end the run.

`slice` is no longer on the path to a first result. The journey is `setup` · `connect` ·
`run`.

Not `LIVE-OBSERVED`: the plan, the refusals and the composition are proven; no collection
has been performed against a tenant.

### FIRST-RUN-005 — the front door is the journey — `CONTRACT-PROVEN`

**authority:** repository · **next action:** none: `CONTRACT-PROVEN`

**Done, 2026-08-20.** Install is at the top and the journey follows it; the
epistemology, which used to run for a hundred and forty lines before a reader could
install anything, follows both. The command table carries every shipped command. The
opening path reaches a tenant, and the fixtures are a section of their own for a reader
who has none.

**Three false claims went with it**, all in the section a sceptical reader reads first:
`Two rules` where there are twenty, `One profile` where there are nine, and application
authentication described as not implemented after it had been implemented and shipped.
Counts are no longer restated in prose at all — `list-rules`, `doctor` and `--help` are
the answer, and a number in a README is a second place for it to be wrong.



## A capability is not shipped until it is installable

> **Merging a collector is not shipping it.** A capability slice reaches
> `SHIPPED` when the release that carries it is published to the public index and
> proven installable from there by `tools/post-release-check.sh` — not when the
> branch is green, and not when a local wheel works.

The trigger is a public capability: a contract, a rule, a collector or a CLI
surface that somebody outside this repository consumes. An internal fix is not one.

Until the current slice is `SHIPPED`, no new collector starts here. An engine that
keeps adding surfaces ahead of its own published releases accumulates capability
nobody can install, and the gap is invisible from inside the branch that created it.

```text
FIRST-RUN       ACTIVE

IDENTITY-CA-001 FROZEN, contract unchanged

Slice           OPEN
```

`ACTIVE` becomes `SHIPPED` when the release is on the public index and the
post-release gate has proven it from there. Only then does `IDENTITY-CA-001` resume, and
`IDENTITY-APPS-001` after it.

## MIGRATION-VERIFY-001 — what a move actually moved

**authority:** owner · **next action:** frozen by the FIRST-RUN freeze; resumes when it ships

**State:** contract and comparison landed on `public-manifest-001`; collectors not
started. Anybody picking this up starts at *What is missing*, in that order.

### What exists

- `migration-read/1.0.0` — the input contract. One read of an estate at one
  moment: what was found, and what could not be reached.
- `migration-verification/1.0.0` — the record. Two reads named by digest, the
  dimensions compared, and one finding per item that did not pass silently.
- `src/m365_governance/migration.py` — comparison, derived dimensions, the
  Markdown report, and four coherence rules a schema cannot express.
- `migration-verify BASELINE VERIFICATION [--out] [--report]` in the CLI.
- `tests/test_migration.py`, and a synthetic read pair under
  `data/fixtures/migration/`, classified in the fixture registry.

### The rule the whole slice turns on

**A migration cannot be verified after the fact.** Decommissioning the source is
the point of the exercise, so a record produced at sign-off has nothing left to
compare against. Every document names two reads, and a baseline that is not
earlier than the verification is refused rather than recorded.

### Which source each dimension needs

**Not a decision — a consequence.** Established by running the connector against
a real estate and reading what came back:

| Dimension | Minimum source |
|---|---|
| Presence · Count | a **search** surface |
| Size · Authorship · Versions · Permissions · Sharing links | **Graph** |
| Content | a **download**, and nothing weaker: equal size is not equal content |

That table answers *what is the next collector* without anybody choosing. A
search surface establishes that items exist and how many; every other dimension
needs a source that carries the attribute.

**And a read declares what its source can never provide.** `unsupported` on a
read separates two sentences that look identical from the outside: *this API
never exposes authorship* and *this run did not ask for it*. The first is a
permanent limit of the method, the second is a fixable gap, and a product that
renders them the same way reports structural limits as execution failures the
moment a second connector appears.

### The cost model, measured rather than assumed

| Request | Buys |
|---|---|
| one **per page** of a folder listing | size · authorship · content digest |
| one **per item** | versions |
| one **per item** | permissions · sharing links |

**Graph cannot expand permissions on a driveItem or a collection of them** — it
is documented, not a limitation of this client. On a quarter of a million items
that is a quarter of a million requests, so the expensive two are opt-in and a
read that did not ask for them records `out-of-scope`, which reads differently
from a gap.

**The digest is `quickXorHash`**, the only hash Graph guarantees across both
OneDrive flavours; `sha256Hash` is documented as unsupported. It compares
against another Graph read and means nothing against a SHA-256 of the same
bytes, so the read records the algorithm and the comparison refuses to cross
two.

### What a tenant has confirmed, and what it has not

**Observed, 2026-08-17, through an interactive Microsoft 365 connector against a
real tenant.** No identifier, drive, path or file name from it is recorded here.

| Confirmed | |
|---|---|
| Traversal | an account carries several drives; children are folders or files, and the producer's folder-versus-file branch matches what the service returns |
| Size | present on real items, as an integer, and it is the shape the producer reads |
| Scale | one drive returned a total in the hundreds of thousands of items, against a surface that pages fifty at a time. The coverage a read writes for that is not hypothetical |

| Not confirmed, and why |
|---|
| **Authorship, digest, versions, permissions.** The connector renders a summary; it does not expose `createdBy`, `file.hashes`, versions or permissions at all. Nothing about those four is established by having looked |
| **The collector's own path.** The connector is a different surface from `GraphReader`. Confirming a field through one does not establish that the other reads it, and treating it as though it did is the substitution this repository's evidence ranking exists to prevent |

**Observed again, 2026-08-18, same surface, same discipline.** Three facts the
first observation did not carry, and none of them changes what is confirmed
above:

| What a real estate holds that no fixture models | |
|---|---|
| Pre-platform timestamps | items whose `lastModifiedDateTime` is 1984 and 1985, decades before the platform existed. They are a package manager's deterministic timestamps, preserved through upload. A read that reasons about item age has to survive dates that predate the service, and the fixture corpus contains nothing older than the project |
| Depth and repetition | seventeen path segments, 215 characters, with `node_modules` nested inside `node_modules`. Well inside the producer's 64-level guard, which is now a measured margin rather than a chosen number |
| Scale, again | 24,129 items answered a single search term on one drive. Consistent with the earlier total, and it is the shape of the estate a first read will meet |

| Not confirmed, and one new reason why |
|---|
| **A summary surface's nulls are not the service's nulls.** The connector returned `size: null` on every item in a search result, while the earlier observation established size as present and integer on real items through the same connector's item view. Two projections of one service disagreeing about a field is exactly why a field confirmed through one surface says nothing about another |

**So `migration-read` still has no positive live read**, and the small drive that
account carries is the known estate to run it against first.

### Least privilege, measured on 2026-08-18

A dedicated application identity was registered for this, with no permissions
at all, and permissions were added only when a named operation failed. No
tenant identifier, host or site name is recorded here.

**Two facts about the setup, before any permission.**

`PnP.PowerShell 3.3.0` accepts a client secret **only** in the retired ACS
parameter set. Entra application-only requires a certificate, and an
administrator following a secret-based instruction gets a parameter-binding
error rather than an authorisation one. That belongs in the connect
documentation before it belongs anywhere else.

`Connect-PnPOnline` **succeeds with zero permissions**. Connection is
authentication; nothing about authorisation is established by connecting, and
a collector that treats a successful connect as a green light is reading the
wrong signal.

**Measured, with the SharePoint application role `Sites.Read.All` and nothing
else.**

| Operation | Result | Capability it serves |
|---|---|---|
| `Get-PnPWeb` | established | activity, agents, classification, modernity, owners, sharing |
| `Get-PnPSite` | established | classification, sharing |
| `Get-PnPList` | established | modernity, permissions |
| `Get-PnPListItem` | established | permissions |
| `Get-PnPSiteCollectionAdmin` | established | owners |
| `Get-PnPFeature -Scope Web` | established | modernity |
| `Get-PnPPage` | established | modernity |
| `Get-PnPApp` | established | spfx |
| `Get-PnPCopilotAgent` | established | agents |
| `Get-PnPTenantSite` | refused | sites |
| `Get-PnPTenant` | refused | tenant-sharing |

**Nine of the eleven collector operations need `Sites.Read.All` and nothing
more.** That is the minimum available for them: the SharePoint application
roles offer nothing narrower that still reads a site, so it is recorded as the
floor rather than as a search that gave up.

The two refusals are clean authorisation errors, `Attempted to perform an
unauthorized operation`, on the tenant administration surface as well as the
site one, so the surface is not the reason. The collector's failure classifier
maps that message to `permission-denied` and not to `missing`, which was
checked rather than assumed.

**A correction to what the manifest publishes.** The `sites` capability
declares `AllSites.FullControl`, and that value does not exist among the
SharePoint application roles: it is a name from the retired ACS model. What
the two tenant reads actually need is unestablished, and the next step is one
role wider, `Sites.Manage.All`, then `Sites.FullControl.All` only if the
narrower one is refused.

**Not established, and why.** Granting the wider role was refused by this
machine's own guard rails, so the tenant pair stops here. Nothing about
`Sites.Manage.All` is claimed, in either direction.

### What is missing, in order

1. **Live validation** of `migration-read` against a tenant with a Graph token,
   under the same observation rules as every other collector here. Everything
   below it is blocked on this.
2. **Scale.** The enumeration follows the service's own next links, and nothing
   has yet run it against an estate of the size the connector measured.
3. **Content across systems.** `quickXorHash` is a Microsoft hash; a move from
   a file share has nothing to compare it to. That needs a download and a real
   digest on both sides, and it is deliberately not started.
4. **Release**: the capability is not shipped until it is installable from the
   public index.

### What is deliberately not here

No remediation, no ranking, no score. The record never claims something was not
migrated when it could not be read: that is `unknown`, with the side and the
reason, and it is the single behaviour the contract exists to protect.

## PUBLIC-MANIFEST-001 — one published description of what this engine can do

**authority:** owner · **next action:** frozen by the FIRST-RUN freeze; resumes when it ships

**Accepted 2026-08-17, and it runs before the Identity surface expands further.**

### Question

> What does this engine collect, decide and promise, in one document a consumer
> can read without cloning the repository?

### Why

The facts exist and are scattered across the places that produce them: the
slice registry knows the collectors, the rule files know the rules and their
basis, the schemas know the contracts, `docs/COLLECTOR-LIVE-MATRIX.md` knows
what has been proven against a tenant, and the source audits know the
permissions and limitations. Nothing joins them, so every consumer that wants
the whole picture rebuilds it by hand — and a hand-built copy of a fact this
repository owns is a second authority that goes stale silently.

### Scope

Publish a versioned contract carrying, for each capability: its collectors, the
Microsoft API each reads, the permissions each requires, the evidence contracts
it produces, the rules that consume it with their basis and limitations, the
relationships between them, and what live validation has established. Generated
from the registry, the rules, the schemas and the matrix — never hand-written,
and refused by the gate if it drifts from what it describes.

`registry.contract(name)` and the existing schema bundle are the pattern; the
manifest is one more contract published the same way, not a new mechanism.

### What it is not

Not state, not a queue, not a roadmap. A capability appears in it when it is
implemented and shipped, and never because it is planned.

## Why this slice

The next service is Microsoft Entra ID, starting with the access-policy surface that
can support several governance conclusions. This is one vertical capability, not a
set of unrelated collectors.

SharePoint tenant sharing, site sharing, site inventory and site classification
already exist. They are regression surfaces, not work to rebuild. Microsoft Secure
Score is a Microsoft projection and never replaces Engine evidence or rules.

## Question

> What access-policy configuration did this identity observe for the tenant, what
> could it not read, and which defensible conclusions can the Engine draw from the
> current Microsoft contract?

Read the specification before implementation. If a field cannot support a conclusion,
collect it only when the report is an explicit consumer and says exactly what was
observed. Never invent a threshold or interpret an absent value from its shape.

## Official surface to inspect

Checked on 2026-08-17; re-open the live pages before coding:

| Surface | Read operation | Least application/delegated permission documented |
|---|---|---|
| Conditional Access policies | `GET /v1.0/identity/conditionalAccess/policies` | `Policy.Read.All` |
| Named locations | `GET /v1.0/identity/conditionalAccess/namedLocations` | `Policy.Read.All` |
| Security Defaults | `GET /v1.0/policies/identitySecurityDefaultsEnforcementPolicy` | `Policy.Read.All` |

Authentication-strength details used by a policy are embedded in
`grantControls.authenticationStrength`; they are not a fourth collection endpoint.
Preserve the embedded identifier, policy type, satisfied requirements and allowed
combinations returned by the policy. Do not add a separate authentication-strength
request unless a later accepted slice establishes a distinct consumer and re-audits
its current contract.

`Policy.Read.All` is the documented least delegated and application permission for
all three operations above, with no higher-privileged alternative documented. A
delegated identity also needs one of the directory roles accepted by the current
operation documentation, such as Global Reader, Security Reader or Conditional
Access Administrator. Permission without an accepted directory role is denial, not
an empty tenant. The Graph host is configuration because the four supported national
clouds use different endpoints.

Primary references:

- <https://learn.microsoft.com/graph/api/conditionalaccessroot-list-policies?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/conditionalaccessroot-list-namedlocations?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/identitysecuritydefaultsenforcementpolicy-get?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/resources/policyroot?view=graph-rest-1.0>

`docs/EXTERNAL-SOURCES.json` already permits factual discovery and short attributed
reference to Microsoft Learn. Copy no Microsoft prose or sample code.

## Scope

### A. Source and collection-path audit

Before production code, record in the durable slice evidence:

1. exact v1.0 endpoints and response resource types;
2. least privilege separately for delegated and application identity;
3. supported national clouds and licensing prerequisites;
4. pagination and consistency behaviour;
5. throttling (`429`/`Retry-After`), transient failure and retry limits;
6. `401`, `403`, absent resource, empty collection and unsupported-property meaning;
7. evolvable enums and `unknownFutureValue` handling;
8. fields omitted unless explicitly selected or returned only with extra permission;
9. which rule basis is requirement, documented guidance, documented limit or convention;
10. every referenced identifier that the slice can and cannot resolve.

The source audit is the first internal step, not a communication checkpoint or a
stopping point. If it changes the question, correct the durable contract and continue
directly into implementation. Do not send an interim report or wait for acknowledgement.
Escalate only a material product decision that the sources and existing architecture
cannot settle.

The initial audit left four live questions for tenant validation: actual licensing,
pagination observed in this tenant, effective throttling limits and whether different
accepted delegated roles return different fields. They do not block the provider,
fixtures, contracts, rules, tests or subsequent queue items. Record only what the live
run establishes; do not promote an observation into Microsoft-wide semantics.

### B. Graph read-only acquisition

Add the smallest provider boundary that can read Microsoft Graph without coupling the
Engine model to terminal text or to the existing PnP collector. Preserve the current
SharePoint path unchanged.

The provider must:

- permit only `GET` for this slice and reject mutation structurally;
- accept externally supplied authentication; never create consent, credentials,
  applications, secrets or certificates;
- record source API, identity kind and granted scopes/app roles without secret values;
- derive `observed_tenant_id` only from the authenticated session/token claim;
- keep public `resolved_tenant_id` distinct from observed session identity;
- follow pagination and bounded `Retry-After` behaviour;
- return structured unavailable/partial results rather than parsing terminal prose;
- preserve requested/completed/unavailable coverage in the collection manifest;
- never translate permission denial, unsupported surface or licence absence into an
  empty compliant tenant.

### C. Product capability

Expose one CLI slice named `conditional-access` that collects, in the same run:

1. Conditional Access policies;
2. named locations referenced by those policies;
3. Security Defaults state when the official read path and permission are proven;
4. authentication-strength details embedded in each policy response.

Unresolved users, groups, roles, applications or locations remain stable native IDs
with explicit resolution state. This slice does not silently add directory-wide
inventory to make a label look friendly.

The output must be consumable by:

- JSON/Markdown/HTML report as an access-policy inventory;
- Assessment and RunSet;
- comparison/diff across two assessments;
- governance rules whose Microsoft basis survives the audit.

An inventory item may ship without a rule only when the report consumer is named and
the documentation explains why Microsoft provides no normative conclusion. No rule
is created merely because a field exists.

### D. Evidence and tests

Use only synthetic public fixtures. Cover at least:

- enabled, disabled and report-only policies;
- include/exclude targets and an unresolved target;
- IP and country named locations without real IPs or names;
- built-in and custom authentication strength references when supported;
- Security Defaults enabled, disabled and unavailable when supported;
- empty tenant distinguished from permission denied;
- delegated `Policy.Read.All` without an accepted directory role distinguished from
  an empty tenant;
- pagination;
- `429` with `Retry-After` and bounded exhaustion;
- `401`, `403`, malformed response and partial second page;
- an unknown future enum preserved without becoming pass;
- two tenants proving no cross-tenant combination;
- structural proof that no mutating HTTP method is reachable;
- collection manifest, Assessment, report and diff;
- clean installed-wheel execution outside the checkout.

Tests assert outcomes and provenance, not mocks alone. A negative test must show that
removing pagination, tenant isolation, permission-denied handling or the read-only
guard makes the contract fail.

## Authorised live observation

The owner authorised read-only tests against a named tenant and its
administration surface. **The two addresses are not written here.** They were
recorded in this file until 2026-08-18, which is a repository that ships to
anyone: a host name is a live tenant value like any other, and the sentence
under them already said not to publish one. The addresses live with the owner;
what belongs here is that the authorisation exists.

Do not publish the directory ID, a host, or any other live tenant value.

Use existing authentication only, in this precedence:

1. `ENTRAID_APP_ID`;
2. `ENTRAID_CLIENT_ID`;
3. `AZURE_CLIENT_ID`;
4. existing managed PnP configuration.

Never print the selected value. Never create missing configuration. The current
SharePoint regression uses the established interactive flow without `--device-login`.

For Graph, inspect existing consent only after the provider exists:

- consent sufficient: collect read-only and record a sanitised result;
- missing `Policy.Read.All`: record `BLOCKED_OWNER_POLICY_READ_ALL` for live
  observation only, then finish code, fixtures, contracts, rules, reports and PR;
- no authentication configuration: record `BLOCKED_OWNER_AUTH_CONFIG` for live
  observation only and continue the same way.

No live hostname, tenant ID, user, group, application ID, policy name, named-location
name, IP range or other identifier enters the public repository. Validate live output
in an ephemeral directory, retain only non-identifying states/counts and destroy it.

## Explicit exclusions

Do not include in this slice:

- app registrations, enterprise applications, service-principal inventory;
- OAuth grants or app-role assignments;
- per-user authentication methods or MFA registration reports;
- PIM, privileged-role assignments, administrative units or break-glass discovery;
- cross-tenant access or external identities;
- risky users, risky sign-ins or sign-in logs;
- remediation, consent, policy simulation or any write operation;
- Exchange, Teams, Intune, Defender, Purview, Power Platform or Copilot expansion.

Configuration, access control and telemetry remain separate evidence dimensions.

## Definition of Done

`IDENTITY-CA-001` closes only when all applicable items hold:

- [ ] official audit above is recorded with review date and precise permissions;
- [ ] Graph provider is read-only by construction and independently tested;
- [ ] `conditional-access` is reachable from the installed CLI;
- [ ] provenance and coverage distinguish observed, partial, denied and unsupported;
- [ ] policies and dependencies are lossless, tenant-scoped and diffable;
- [ ] every rule has collectable evidence and an attributed Microsoft basis;
- [ ] inventory without a rule has an explicit report consumer and limitation;
- [ ] Assessment, JSON, Markdown, HTML and comparison consume the new resources;
- [ ] synthetic fixtures contain no tenant-derived identifiers or copied values;
- [ ] focused tests, full Engine release contract and clean-clone/wheel checks pass;
- [ ] authorised live observation passes or carries one exact owner-only blocker;
- [ ] README/reference/CLI help and `docs/EXTERNAL-SOURCES.json` are current;
- [ ] branch, SHA, checks, evidence and next action are recorded in the PR;
- [ ] PR is mergeable, clean and has no unresolved review; the Executor does not merge.

## RULE-MESSAGES-001 — editorial debt in the `unknown` messages

**authority:** owner · **next action:** frozen by the FIRST-RUN freeze; resumes when it ships

**State:** measured, not started. Owner decision 2026-08-20: a pass of its own,
rule by rule.

Two phrasings survive across the SharePoint rule set. Both were found by measuring
the real single-site report whole, and both were left alone in `6283b44` because
the slice that found them was about the renderer.

### What was measured

Nineteen rules, and three of them carry both.

| | rules |
|---|---|
| `the evidence beside this finding says which` (6) | `SPO-CLASS-004`, `SPO-LIST-002`, `SPO-LIST-003`, `SPO-SHARE-002`, `SPO-SHARE-005`, `SPO-SITE-003` |
| `This is not a pass` (16) | `SPO-ACTIVITY-001`, `SPO-CLASS-001`, `SPO-CLASS-002`, `SPO-CLASS-003`, `SPO-LIST-001`, `SPO-LIST-002`, `SPO-MODERN-001`, `SPO-MODERN-003`, `SPO-MODERN-004`, `SPO-SHARE-001`, `SPO-SHARE-002`, `SPO-SHARE-003`, `SPO-SHARE-004`, `SPO-SITE-002`, `SPO-SITE-003`, `SPO-SPFX-001` |
| both (3) | `SPO-LIST-002`, `SPO-SHARE-002`, `SPO-SITE-003` |

The first points at something the run-set report does not print. `to_markdown`
renders an `Evidence:` line beside each result and `many_to_markdown` does not,
and `many_to_markdown` is the path `assess` writes for. The second sits under a
heading that already reads **Unknown**.

`SPO-SITE-001` was corrected in `6283b44` under an explicit owner instruction and
is the worked example.

### How it is done, and how it is not

**Rule by rule, reading each message.** A global substitution is refused here: some
of these sentences carry the only statement of what was not established, and
deleting the clause around the phrase would remove information a reader needs while
appearing to be a formatting change. The measurement above is a list of places to
look, not a list of edits.

Each message must stand on its own: name the real paths into `unknown` without
pointing outside itself, and without restating the outcome the label already
carries. The rule schema forbids interpolating a value into an `unknown`,
`not_applicable` or `invalid_evidence` message, and that constraint holds — a field
cannot be both the reason the rule could not decide and a value the rule prints.

Wording, so no rule version moves. `docs/CHANGE-POLICY.md` settles that.

### Done when

- [ ] every message listed above has been read and either rewritten or kept with the
      reason recorded in the PR;
- [ ] no message points at evidence the run-set report does not render;
- [ ] no message restates its own outcome label;
- [ ] `tests/frozen/single-site-report.md` is updated deliberately if the document
      changes, and its diff is the review;
- [ ] the density gate in `tests/test_report_density.py` is re-measured;
- [ ] the Engine release contract passes.

## Continuous execution constitution

### Selection and continuation

1. The first queue item without durable `QA_READY` evidence is the current slice.
2. Complete it vertically, push its branch, open or update its PR, follow CI and
   resolve review findings.
3. A pending PR, CI run, review or authorised merge is not idle time and does not
   block the next slice. Branch the next slice from the last proved head and declare
   the dependency in its PR. After an upstream merge, rebase and prove the isolated
   delta.
4. Keep at most one implementation slice active and one completed slice awaiting
   integration. Waiting for external state does not require a conversation: monitor
   it while continuing the current eligible work in the foreground.
5. Never merge, deploy, publish, create consent, change tenant state or manufacture
   credentials. Those actions remain outside execution authority.
6. Do not stop after an inventory endpoint, collector or test. Continue until the
   capability is reachable through the installed product and every named consumer.
7. Do not ask the owner which accepted slice comes next. This file answers that
   question. Ask the Auditor only when a contradiction changes product meaning or no
   safe, documented path remains after the blocker rules below.
8. Internal items, phases, source audits and checkpoints never produce a hand-off or
   pause. Continue within the same turn and working sequence until the whole slice is
   `QA_READY` or an exact blocker exhausts every unaffected action. Progress messages
   are permitted only when execution continues; they never request acknowledgement.

### Common vertical contract for every slice

Every queue card inherits this sequence and is incomplete if any applicable step is
missing:

1. Re-open the current official Microsoft operation and resource documentation before
   implementing each surface; search results, error messages, remembered behaviour and
   documentation for another tool are not authority.
   Record review date, API version, availability, national-cloud support, licence,
   least delegated and application permissions, pagination, throttling, absence,
   partial-response and evolvable-enum semantics. Do not code from memory.
2. Record which source answers which question. Microsoft Learn owns Microsoft API
   operations, permissions, national clouds, resource semantics, limits and guidance.
   A third-party tool is governed by its own documentation at the pinned version.
   Runtime observation proves only what that run returned.
3. Inspect existing repository contracts and reuse the owning provider, resource,
   provenance, manifest, Assessment, RunSet, rule, report and comparison patterns.
   Extend existing SharePoint collectors; never duplicate them.
4. Add the smallest read-only acquisition boundary. Only documented read operations
   are reachable. Authentication is supplied externally. Preserve source endpoint,
   API version, identity kind, coverage and granted permission names without values.
5. Model observed evidence losslessly and tenant-scoped. Keep configuration, access
   control and telemetry as separate evidence dimensions. Empty, denied, unsupported,
   unlicensed, partial and failed are different states and never imply compliance.
6. Name the consumer before collecting a field: inventory/report, Assessment,
   comparison or a rule with an attributed normative basis. A convenient field is
   not by itself a defensible rule.
7. Expose the capability through the installed CLI and JSON, Markdown and HTML where
   the resource is reportable. Include it in Assessment/RunSet and comparison when
   meaningful. A hidden module is not delivery.
8. Test with synthetic fixtures: happy path, empty, `401`, `403`, unsupported or
   unlicensed, pagination, `429`/`Retry-After`, partial later page, malformed response,
   unknown future values, two-tenant isolation, provenance, manifest, installed wheel
   and a negative proof that the principal safety contract can fail.
9. Perform authorised read-only live observation when authentication, permission and
   licence already exist. Keep all live values ephemeral and publish only sanitised
   state. Never turn live observation into a prerequisite for deterministic tests.
10. Update the owning public contract, CLI help and external-source register. Do not
   publish tenant identifiers, private consumer information, commercial strategy or
   copied vendor prose.
11. Run focused tests while iterating, then the complete Engine release contract once
    the delta is stable. Do not repeat a green full gate without a changed affected
    input. Shut down build servers after heavy runs and run only one heavy gate at a
    time.
12. Record branch, head SHA, exact checks, sanitised evidence, exclusions and any
    local blocker in the PR. Reach `QA_READY`, then immediately select the next queue
    item. The Executor does not merge.

### Localised blockers

A missing external prerequisite blocks only the affected live proof or conclusion,
not fixtures, implementation, reports, tests, PR delivery or the next accepted slice.
Use one exact durable state:

- `BLOCKED_OWNER_AUTH_CONFIG` — no existing authentication path;
- `BLOCKED_OWNER_CONSENT_<PERMISSION>` — the exact documented read permission is absent;
- `BLOCKED_EXTERNAL_LICENSE_<SERVICE>` — the tenant lacks the required licence;
- `BLOCKED_EXTERNAL_API_<SURFACE>` — the official service is unavailable or failing;
- `BLOCKED_OWNER_BETA_API_<SURFACE>` — only a beta contract exists and adopting it
  changes the public stability promise;
- `BLOCKED_NORMATIVE_BASIS_<CONCLUSION>` — evidence is collectable but no authoritative
  basis supports the proposed conclusion.

Record the blocker in the PR and continue all unaffected work. Call the Auditor only
for an unresolved authority contradiction, a new write operation, customer-data risk,
public API break or product meaning that cannot be settled by the repository owner
contracts and current official sources. The Auditor answers governance questions; it
does not implement the slice.

## Accepted execution queue

The owner accepted this entire ordered queue on 2026-08-17. The first ten items are
the value-first wave and retain their exact order. All later items are also accepted
and continue automatically. An item includes only what official, supported contracts
can prove; unsupported sub-surfaces receive an exact local blocker rather than an
invented implementation.

### Wave 1 — highest-value surfaces

#### 1. `IDENTITY-CA-001` — Conditional Access

Use the detailed contract above: Conditional Access policies, named locations,
Security Defaults and referenced authentication strengths. Do not absorb the later
Identity cards.

#### 2. `IDENTITY-APPS-001` — applications and enterprise applications

Inventory app registrations and service principals, including ownership, publisher,
verified-publisher state, sign-in audience, credential metadata without secret
material, service-principal enablement and assignment requirements. Resolve references
between applications and enterprise applications. Use current Microsoft Graph v1.0
directory surfaces and independently verify the least read permissions. Consume the
result in inventory, Assessment, reports and comparison. Do not add/delete credentials,
grant consent or change applications.

#### 3. `IDENTITY-OAUTH-001` — OAuth consent and app-role grants

Collect `oauth2PermissionGrants` and applicable app-role assignments through their
current official Graph surfaces. Resolve client, resource, principal, scope/app role,
consent type and expiry where the contract supplies them, using `IDENTITY-APPS-001`
resources rather than recollecting directory objects. Distinguish delegated consent,
application permission and assignment. Provide inventory, Assessment, report,
comparison and only rules with an attributed Microsoft basis. Never grant or revoke
consent.

#### 4. `EXO-MAILFLOW-001` — Exchange mail flow

Audit and implement the supported read-only Exchange Online path for accepted domains,
remote domains, transport rules, inbound/outbound connectors and organisation-level
SMTP AUTH or legacy-auth settings where officially available. Preserve rule order,
enabled state and conditions/actions without exposing message or address data. Record
PowerShell module/version and required roles separately from Graph permissions. Provide
inventory, Assessment, reports and comparison. Do not change mail flow or send mail.

#### 5. `SPO-EXTERNAL-001` — SharePoint external sharing

Reuse the existing tenant-sharing and site-sharing collectors. Measure and extend only
verified gaps required to explain effective external sharing: tenant/site capability,
default link behaviour, anonymous-link availability and external-user exposure where a
supported read surface exists. Preserve tenant-versus-site precedence and `unknown`
when link usage cannot be observed. Add rules only from explicit Microsoft limits or
guidance. Test the two authorised SharePoint host forms without publishing live data.

#### 6. `SPO-SITES-001` — SharePoint and OneDrive site inventory

Reuse the current site inventory and classification resources. Add only verified,
consumer-backed gaps among owners, storage quota/usage, sensitivity label assignment,
versioning and lifecycle metadata supported by the chosen API. Represent OneDrive and
SharePoint site types explicitly. Avoid content enumeration and personal data. Prove
pagination, duplicate/canonical URL handling, inaccessible sites and comparison.

#### 7. `TEAMS-ACCESS-001` — external and guest access

Audit Microsoft Graph and Teams PowerShell ownership before choosing a path. Collect
tenant external-access, guest-access and team-creation governance settings available
through supported read contracts. Do not infer policy enforcement from membership or
guest presence. Record required roles, licences and PowerShell versions. Provide
inventory, Assessment, reports and comparison; never create a team or change policy.

#### 8. `INTUNE-COMPLIANCE-001` — compliance and device posture

Collect compliance policies, assignment scope, device-compliance summaries, enrolment
restrictions and a privacy-minimised device inventory through current Microsoft Graph
device-management contracts. Verify Intune licence and permission requirements and
gate every beta-only dependency explicitly. Keep policy configuration separate from
device evaluation. Do not collect unnecessary user/device identifiers or perform any
device action.

#### 9. `DEFENDER-SCORE-001` — Microsoft Secure Score

Collect the supported Secure Score control profiles, score snapshots and related
recommendations with current security API permissions and retention semantics. Label
scores as Microsoft projections: they never replace Engine evidence, provenance or
rules. Preserve unavailable products and licensing gaps. Provide trend/comparison and
reports without claiming that a score proves compliance. Do not update control state.

#### 10. `PURVIEW-LABELS-001` — sensitivity-label governance

Audit supported Microsoft Graph and Purview PowerShell read paths for label definitions,
publication/policy state and auto-labelling configuration. Keep tenant label governance
separate from existing SharePoint label assignment. Record security/compliance roles,
licence and beta dependencies. Provide inventory, Assessment, reports and comparison.
Do not publish labels, label content or change policies.

### Wave 2 — Identity completion

#### 11. `IDENTITY-AUTH-001`

Authentication-method policy, method configurations, registration/capability reporting
and MFA registration coverage. Aggregate privacy-sensitive user results by default;
retain no user identity unless an existing public contract explicitly requires it.
Separate policy enabled from user registered and capable. Include Security Defaults
only by reference to `IDENTITY-CA-001`.

#### 12. `IDENTITY-PRIV-001`

Directory roles, active and eligible assignments, PIM policy/configuration,
administrative units and declared emergency-access-account criteria. Never identify a
break-glass account by display name or guesswork: report configured evidence or
`not established`. Separate standing privilege, eligibility and PIM elevation history.

#### 13. `IDENTITY-XTENANT-001`

Cross-tenant access defaults and partner overrides, tenant restrictions, external
collaboration settings and B2B/B2C identity configuration supported by current APIs.
Do not enumerate external people unless essential and contractually owned; prefer
configuration and aggregate evidence.

#### 14. `IDENTITY-RISK-001`

Risky-user, risky-sign-in and sign-in-summary telemetry. Record licence, retention,
delay and permission limits; use bounded, privacy-minimised time windows. Telemetry is
not configuration. No identity names, IP addresses or raw sign-in events enter public
fixtures or durable evidence.

### Wave 3 — Exchange Online completion

#### 15. `EXO-PROTECTION-001`

Anti-spam, anti-phishing, Safe Attachments and Safe Links policy configuration,
including priority and assignment where supported. Preserve Microsoft-managed defaults
and unsupported licence states. Never submit or detonate content.

#### 16. `EXO-MAILBOX-001`

Mailbox forwarding, mailbox permission exposure, shared-mailbox posture and per-mailbox
SMTP AUTH state. Default output is aggregate/privacy-minimised; access to individual
mailbox identity requires an existing public consumer contract. No mailbox content or
addresses in fixtures/evidence.

#### 17. `EXO-DOMAIN-AUTH-001`

DKIM configuration plus observed DMARC and SPF DNS records for accepted domains.
Separate Exchange configuration, DNS observation and normative conclusion. Bound DNS
timeouts and preserve indeterminate results; never alter DNS.

### Wave 4 — SharePoint and OneDrive completion

#### 18. `SPO-CONTROLS-001`

Idle-session controls, restricted access control, tenant/site default-link settings and
site classification governance. Reuse earlier sharing and site evidence and model
effective precedence without duplicating collectors.

#### 19. `SPO-LIFECYCLE-001`

Versioning, storage quotas and supported site/OneDrive lifecycle controls. Distinguish
configured policy, current state and observed usage; do not inspect file content or
invent a lifecycle conclusion from age alone.

### Wave 5 — Teams completion

#### 20. `TEAMS-POLICIES-001`

Messaging, meeting and recording policy configuration and assignment coverage through
supported read surfaces. Separate global defaults, group/user assignment and effective
policy where Microsoft exposes it. Collect no meeting/chat content.

#### 21. `TEAMS-APPS-CHANNELS-001`

App permission/setup governance, third-party app availability and aggregate private/
shared-channel governance. Do not enumerate messages or expose team/channel names.

### Wave 6 — Intune completion

#### 22. `INTUNE-CONFIG-001`

Configuration profiles, Windows Update rings, BitLocker, Defender and ASR policy
configuration plus assignment coverage. Preserve platform/type-specific settings and
unknown future values. Never change or sync a device.

#### 23. `INTUNE-AUTOPILOT-001`

Device enrolment and Autopilot profile/deployment governance. Reuse device inventory,
minimise hardware identifiers and separate registered, assigned and deployed states.

### Wave 7 — Defender completion

#### 24. `DEFENDER-OPERATIONS-001`

Incidents, alerts, exposure recommendations, TVM recommendations and aggregate email,
endpoint, ASR and identity-protection posture through licensed supported APIs. Use
bounded windows and privacy-minimised evidence. Never close incidents or change
remediation state.

### Wave 8 — Purview completion

#### 25. `PURVIEW-DLP-RETENTION-001`

DLP, retention, data-lifecycle and auto-labelling policy configuration, publication and
assignment. Collect policy metadata, not protected content. Distinguish configured,
published and enforced where the API permits.

#### 26. `PURVIEW-INVESTIGATION-001`

Inventory-only governance for Insider Risk and eDiscovery cases/settings through
supported, least-privilege read contracts. Do not collect case content, custodians or
communications. If privacy-safe inventory has no defensible consumer, close it as
`BLOCKED_NORMATIVE_BASIS` rather than widening collection.

### Wave 9 — tenant platform

#### 27. `TENANT-ORG-001`

Licences/subscribed SKUs, verified domains, organisation settings, usage-location
coverage, company-branding configuration and administrative-role coverage. Reuse
Identity role evidence. Do not expose addresses, contact data or branding assets.

#### 28. `TENANT-HEALTH-001`

Service-health and Message Center summaries with bounded time windows, pagination and
retention. Treat both as operational telemetry, not tenant configuration or compliance.
Do not reproduce message bodies when identifiers and status suffice.

### Wave 10 — Power Platform

#### 29. `POWER-INVENTORY-001`

Environments, connectors and privacy-minimised Power Apps/Power Automate inventory.
Record Dataverse/admin API licence and role requirements. Do not execute flows or read
business records.

#### 30. `POWER-GOVERNANCE-001`

DLP policies, managed-environment configuration and tenant-isolation settings with
environment/connector assignment resolution. Never modify environments or policies.

### Wave 11 — Copilot governance

#### 31. `COPILOT-READINESS-001`

Copilot licence allocation aggregates, supported settings, restricted SharePoint
governance and documented semantic-index readiness evidence. Reuse SharePoint sharing,
site and label resources. Do not invent a readiness score or inspect prompts/content.

#### 32. `COPILOT-PLUGINS-001`

Supported plugin/agent governance and oversharing indicators derived from already
owned permission/sharing evidence. Keep configured availability separate from observed
use. Never enable, disable or invoke a plugin or agent.

#### 35. `ENGINE-RUN-CONTRACT-VERSION-001` — `run/4.0.0` means two different things

**State:** `OPEN`. **authority:** repository — this is the executor's to resolve, and
`D51` names this exact case as one that must not be escalated. **next action:** the
version cascade, in one commit.

**What happened, and it was this repository's own rule being missed.** Commit `a9da4fd`
repointed `run.schema.json` from `evidence/3.0.0#/$defs/provenance` to
`evidence/3.1.0#/$defs/provenance`, to carry `tenant.how`. The `evidence` half was done
correctly: `3.0.0` was archived and `3.1.0` published. **The `run` version did not
change.** So a document that validates against `run/4.0.0` today is refused by
`run/4.0.0` as it was yesterday. One identifier, two meanings.

**Why nothing caught it.** Nothing validates a run document on its way out. The engine
computes runs, wraps them in a run set, renders them and drops them, so no run document
ever met a reader holding a different copy of the contract. It surfaced the moment one
did: a bundle written by `run --bundle` was read by an independent consumer holding a
vendored copy of the earlier contract, and its refusal named the clause exactly:

```
the run does not match https://ph7x.com/schemas/m365-governance/run/4.0.0:
  #/properties/provenance/$ref/allOf/0/not/required/0
```

The engine is internally consistent. It is consistent with itself and with nobody else.

**The correction, and its size.** `run` becomes `4.1.0` with `4.0.0` archived exactly as
it was. That cascades, because the version lives in the `$id` and a reference to a
changed contract is a change: `run-set` references `run`, and `assessment` references
`run-set`. Three published contracts, their archives, the generated manifest and two
assessment fixtures. **Eight references to `run/4.0.0` and five files naming
`run-set/4.0.0`**, measured rather than estimated.

**The engine half is done and proven.** Archived, bumped, regenerated, and the release
gate now builds the wheel, installs it into an empty environment outside any checkout,
writes the folder a consumer opens, and reads the version from the installed package
rather than from a literal:

```
the bundle an independent consumer would open
  wrote 3 runs
  3 runs, each with its document, its evidence and its report
  every run declares https://ph7x.com/schemas/m365-governance/run/4.1.0
```

**The consumer half is open, and an attempt at it was reverted rather than left standing.**
What it established, all of it measured:

- Refreshing the vendored bundle and migrating the consumer's expected versions to 4.1.0
  produces a schema-compiler collision: `Type40 already contains a definition for
  JsonPropertyNames`, before a single document is read.
- **The consumer is right to refuse until migrated.** Before the version bump it said
  `declares assessment/4.1.0 and this build reads assessment/4.0.0. Valid and unsupported
  is not something to reinterpret: migrate it explicitly.` That refusal is the mechanism
  working and is exactly what this cascade needed to prove exists.
- Same-major pairs are not inherently fatal: `evidence/3.0.0` with `3.1.0`, and
  `connection/1.0.0` with `1.1.0`, coexist in the vendored bundle today.
- Trimming superseded revisions out of the resolver did **not** clear it, so the cause is
  not the resolver's contents.
- **The cause is not established**, and guessing at it further would be the failure this
  file exists to record. The baseline is green at 146 tests with the unrefreshed bundle.

**One defect found on the way and worth its own line.** `publish-contracts` copies with
`copy2`, which preserves the source's modification time, and MSBuild's `PreserveNewest`
then keeps the older copy already in the build output. **A refreshed contract can silently
fail to reach the binary**, and the symptom is a manifest and a schema file disagreeing
about a version inside `bin/`.

**It is done in one commit or not at all.** A partly bumped contract set is worse than
either state, which is why a first attempt at it was reverted rather than left standing.

**And it is already published.** Any consumer that vendored these contracts holds the
earlier text and will refuse what this engine now writes until it refreshes. That is the
correct behaviour on their side and the reason the cascade is not optional: a published
version is a promise about what a document means, and this one was changed without being
renamed.

**The rule this leaves.** A `$ref` to a version that moved is a version change in the
document that holds the reference. `evidence` was treated that way and `run` was not, in
the same commit, by the same hand.

## SECURITY-RESEARCH — a control can stay true while its conclusion stops following

#### 33. `CUSTOM-SCRIPT-SEMANTICS-001`

**State:** `OPEN`. **authority:** Engine for the wording, owner for the tenant.

**What was checked in this repository on 2026-08-21, before anything was written.**
`DenyAddAndCustomizePages` appears once in the whole tree, in the available-field list
of `docs/COLLECTION-PATH-AUDIT.md`. **No collector reads it and no rule interprets it.**
`SPO-MODERN-003` is the only rule that mentions custom script at all, it does so in its
basis rationale, and its own limitations already say it reads one file name.

**So the first layer has no target, and that is the finding.** There is no rule to
narrow, because there is no claim. The risk is not that this engine over-claims today;
it is that the claim gets written on the day the field is first collected, by whoever
writes that collector, from the name of the setting. The wording is therefore decided
here, before the code exists, which is what the charter asks of a decision.

**When the field is collected, the established fact is this and no wider:**

> Direct custom script insertion through the governed SharePoint custom-script
> capability is blocked for this site.

**And the limitation travels with it:**

> This does not establish that no approved component can render dynamic or externally
> produced HTML or content in the page.

**The hypothesis, which is not a published rule and must not become one before it is
observed:** can approved SPFx components render user- or model-produced HTML in a way
that executes with page and user context?

**Why now.** Copilot in SharePoint generates interactive HTML reports, and since August
2026 dashboards bound to a list that refresh when opened. They arrive as files in a
library. Reaching a modern page from there needs an SPFx component, because the custom
script route is exactly the one being closed - which is the point, and the reason a
public example of somebody bridging the two exists at all.

**The finding this is really about, in one line:** *approved code is not the same as
approved content.* The App Catalog proves a component was approved once. It does not
prove that every payload that component will later interpret passed an equivalent
review, and with a model producing those payloads the gap is no longer theoretical.

**Evidence required before any rule is published:**

- the SPFx packages installed, and whether each is tenant-wide or site-scoped;
- which components render HTML or content from outside their own package;
- the rendering mechanism: iframe with what sandbox, DOM injection, sanitisation;
- the origin of the content and what permission places or changes it;
- the API permissions the package holds.

**The stop rule, and it is the point of the card.** If the content can execute in page
and user context, this is a new security finding. If it is isolated, the limit is
documented and the hypothesis closes. **Neither sentence may be published before the
runtime has been observed.** Microsoft documents that script inserted in a page runs as
the visiting user; nothing found so far establishes the isolation mechanism of any
particular component, and a security conclusion drawn from a plausible mechanism is the
failure this product exists to refuse.

**Next action, and it is not engineering:** reproduce the chain in a test tenant -
Copilot-generated HTML, into a library, rendered by an SPFx component - and inspect the
DOM and runtime. That needs an application registration and read consent in that tenant,
which is identity state and is the owner's to grant. Everything above is done without it.

## BRAND-CENTER — a new evidence family, not another rule

#### 34. `BRAND-CENTER-001` — collect brand center governance evidence

**State:** `OPEN`. **authority:** owner decision 2026-08-21 · **next action:** read-only
collection against a configured brand center. **No rules in this slice.**

**The question this family answers.** *What brand assets are published, who can administer
them, and through which Microsoft 365 distribution boundary are they exposed?*

**Why a family and not a collector.** Three boundaries are involved and they are routinely
read as one:

```
administration boundary  !=  consumption boundary  !=  distribution boundary
```

Site permissions govern who administers. A CDN governs who can retrieve. The consuming
applications govern where an asset appears. One collector producing one blob would let a
rule be written about a missing field and called a governance conclusion, which is the
failure this engine exists to refuse. **Each subcapability declares what it can read and
what it cannot.**

**What the documentation already establishes, so no collector infers it.** One brand
center per organization, created by a Global Administrator, storing through Organization
Asset Libraries on a single designated site. The brand center app requires Public CDN, and
a tenant already using organization assets with Private CDN is instructed to activate the
public one to enable it. Published font files and the font catalog generated with them are
stored publicly, do not respect site classification where the library sits in a Restricted
SharePoint Site, and are reachable by anyone who obtains the URLs. A library created
without a `CdnType` gets the private CDN by default. Written up with its sources at
`/knowledge/sharepoint/what-the-brand-center-publishes/`.

### The six collectors

1. **`brand-center-site`** — authority over the container. Site URL and id, owners,
   members, visitors, external sharing capability, classification where observable, and
   whether `BrandCenter.aspx` is present. Establishes authority over the content container
   and **nothing about distribution**.
2. **`organization-assets`** — which libraries were promoted from a SharePoint library to
   an organization resource. Library URL and id, `OrgAssetType`, audience and permissions,
   association with the brand center, and whether the read was complete or partial.
3. **`brand-assets`** — the published inventory by class: fonts, images, themes, font
   packages, templates. Technical name, location, version or modification, type, published
   state where observable, and the library it came from. **A file existing is not a file
   being consumed, and this collector never says otherwise.**
4. **`cdn-distribution`** — the distribution boundary, read separately from any ACL. Public
   and private CDN enabled state, origins, the origins tied to the brand center's
   libraries, and permitted types where observable.
5. **`brand-managers`** — who can administer. Owners and associated groups, and whether
   administrative capability derives from site permissions or from separate configuration.
   **Where no supported interface exposes it: `not-supported` or `not established`, never
   an inference.**
6. **`brand-consumption`** — where assets are available to be consumed: SharePoint, Office,
   Viva, SPFx tokens. **This one starts as a documented capability rather than a live
   observation**, and becomes an evidence collector only if a supported surface says *these
   assets are currently consumable here*. Declaring that up front is what keeps it honest.

### The evidence shape

```
brand_center
  configured
  site: url, owners, audience
  organization_asset_libraries: [...]
  assets: fonts, images, themes, templates
  distribution:
    public_cdn: enabled, origins
    private_cdn: enabled, origins
  administration: [...]
  coverage: completed, unavailable, partial
```

### Read-only, and the word is not decorative

**Do not publish a font, a theme or any asset to test. Do not change CDN state. Do not
change permissions. Do not add brand managers.** Observe the tenant as it stands. If the
first observation leaves a gap only a write can close - proving a font's reachability on
the public CDN is the obvious candidate - that becomes its own bounded, removable
experiment with its own authorisation, using a fixture font and never a licensed face.

### The questions this is built for, which are not rules yet

- Is a brand center configured?
- Who can administer organization-wide brand assets?
- Which Organization Asset Libraries are published?
- Which brand fonts are distributed through the public boundary?
- Does the brand center site restriction establish the distribution audience of its assets?
- Are there published assets whose distribution model differs from the site's audience?
- Is the brand center administered by a single person or group?
- Are there asset classes whose effective distribution boundary cannot be established from
  the collected evidence?

The last one is the one worth building for. A family that can say *this cannot be
established from what is collectable* is worth more than one that guesses.

### What the user runs

One command, not six. `run` detects a configured brand center and collects authority,
organization assets, distribution and assets in sequence. **No per-collector command enters
the user's path**, and `capabilities --questions` gains the family without anybody needing
to know there are five collectors behind it.

## Programme completion

The queue is complete only when every card is either `QA_READY` with the common
vertical contract satisfied or carries a precisely scoped owner/external blocker that
cannot be resolved inside repository authority. No P0/P1 contract defect, silent
permission gap, inaccessible consumer, untested installed-wheel path or undocumented
partial state may remain. At that point the Executor records one sanitised programme
index linking the PR evidence for all completed cards and returns it to the Auditor for
release-governance review. This is not merge or deployment authority.
