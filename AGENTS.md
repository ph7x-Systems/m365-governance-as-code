# Repository invariants

**This file states what is true of this repository, not who or what happens to
be working in it.** It is versioned and travels with a clone, because a
contributor needs these rules and a reader needs to know the engine is held to
them.

Everything here is enforced by something that runs. Where a rule has a gate,
the gate is named beside it; where it does not, it is because the rule governs
a judgement a gate cannot make.

## What this repository owns

Collectors, evidence, provenance, schemas, rules, findings, assessments,
comparisons, the command line and its published contracts. Website editorial
decisions, desktop experiences and anything commercial are owned elsewhere and
are not described here.

## The invariants

### A published contract is immutable under the same version

A version is a promise about a shape. Editing a schema without moving its
`$id` keeps the promise's name and changes what it promises, and a consumer
that already declared support carries on declaring it while reading something
else. Nothing in a tree can tell that apart from a correct edit: both are a
changed file.

Every version this engine has published is recorded with the digest it was
published under in `data/published-contracts.json`, and a test reads it. Adding
a line is the deliberate act of publishing a version. Changing a line is almost
always the defect the ledger exists to catch.

### A search result does not establish that a population is empty

Absence found by searching is absence *in that search*. An enumerated
population that came back empty and a query that returned nothing are different
facts, and evidence records which one it holds: `population`,
`acquisition_method`, and `populations_not_observed` for what the method cannot
reach.

**An inventory surface defines a population. It does not define existence
outside that population.**

### A generated fixture is not a live observation

Fixtures describe shapes. They are fabricated on purpose, they carry no tenant,
and no count in one is evidence about anything. What a collector does against a
real tenant is recorded per slice in `docs/COLLECTOR-LIVE-MATRIX.md` and
published as a state in the capability manifest, and the states are ordered:
`none`, `negative-only`, `provider-only`, `partial`, `full`. A collector with
green tests and no live run has been proved to behave as somebody believed the
API behaves.

### A capability is not proven until its canonical artefact crosses the
integration boundary

The canonical bundle is where this engine ends. Code that works, tests that
pass and a document that validates are three things that can all be true while
the artefact a consumer opens is unreadable. The proof is the artefact being
consumed, not the code being correct.

### Public documentation describes published behaviour only

A page that instructs somebody to run a command a release does not carry is
documentation of an intention. Where a document names a version, everything it
tells a reader to run exists in that version, or the exception is stated where
the reader meets it.

### `unknown` is never a pass

A rule that cannot reach an answer says so. Missing evidence is not compliance,
a refusal is not a negative result, and an absence is never rounded to zero.
Every absence records whose limitation it is — the implementation, the tenant or
identity, Microsoft, or the caller — because only the first is a defect here.

### An observation and a governance conclusion are different claims

Observing what a tenant contains does not entitle anything to say what it
should contain. A conclusion needs a sentence somebody can defend, and where
Microsoft publishes no normative position there is none: those surfaces are
collected and no rule reads them. Widen what can be observed first; decide what
may be concluded after.

Every rule declares its `basis`, and the basis travels with the finding.

### A presentation layer may explain a contract value and never redefine it

Explaining, grouping, translating and visualising are allowed, and translation
is declared where it happens so a reader can recover the contract value behind
the word they were shown. Renaming `unknown` to something friendlier is
explaining. Deciding `unknown` may be counted as a pass is redefining.

**No layer publishes an aggregate score, percentage or grade.** An aggregate
over complete, partial and unknown observations is the artefact this engine
exists to replace. Coverage is reported as the facts it is made of.

### Live acquisition against a tenant is separately authorized

**Installing or configuring an acquisition dependency never authorizes live
authentication or tenant access.** Not the module, not the package, not the
application registration, not the connection string, not a credential already
cached on the machine. Preparing the means and being permitted the act are
different things, and a dependency that exists in order to reach a tenant is
still not permission to reach one.

Live acquisition requires separate explicit authorization: for that operation,
against that tenant, obtained before it runs. One authorization does not extend
to the next operation, to a second run, or to a different scope, and a session
that already exists is not permission to use it.

Documentary research, offline development, fixtures and tests require none of
this, and reaching for authorization to do them is its own mistake.

This engine acquires no credential, writes nothing to a tenant, and transmits
no tenant evidence anywhere. See `docs/TRUST-MODEL.md`.

### Evidence is ranked, and the ranking is not a formality

Observed runtime or test; then a machine-readable schema or contract; then
primary vendor documentation; then community documentation; then blogs, samples
and issues. **Observation proves what happened, not what it means**: a product
conclusion also needs the contract that defines the meaning. Where evidence
cannot be obtained, the answer is `not established` — never an inference from
an observation that could not be made.

### Everything written here is in English

Code, comments, tests, error messages, tooling, workflows, documentation,
commit messages, pull requests and release text. The exceptions are verbatim
external evidence, quoted as it arrived because changing the text destroys what
it proves, and localized product content, which this repository does not carry.
Enforced by `tools/language-check.sh`, inside the gate.

## The gate

```bash
./tools/release-check.sh
```

It validates the rules, the schemas and their generated models, runs the tests
with coverage, checks the examples, lints, analyses the PowerShell, builds the
wheel, and installs it into an empty environment to prove the product runs from
outside any checkout. **A partial invocation is not a release result.**

After a release, `./tools/post-release-check.sh` proves the published artefact
installs from the public index and runs.

Every commit carries `Signed-off-by` (`tools/dco-check.sh`).

## What this repository does not publish

It documents what the software does, what its evidence establishes, which
contracts it publishes and where it stops. It does not document what is being
built next, in what order, or why. That is not a property of the software.

`m365-governance capabilities --domains` publishes the coverage matrix: which
Microsoft 365 surfaces this engine claims and how far each has been proved,
including the ones it cannot observe at all. It publishes state, never
sequence, and it carries no priority, blocker, estimate or date.
