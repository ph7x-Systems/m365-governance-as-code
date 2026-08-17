# Repository contract

This file is versioned and travels with a clone. It is the entry contract for
any automated executor working in this repository. Human contributors want
`CONTRIBUTING.md`, which this file does not replace.

## Purpose

This repository owns collectors, evidence, provenance, schemas, rules,
findings, Assessments, comparisons, the CLI and its public contracts. It
collects what a Microsoft 365 tenant is configured to do, and decides only what
a written rule says it may decide.

## Sources of truth

- The contracts are the JSON Schemas under
  `src/m365_governance/data/schemas/`. A version is declared once, in the
  schema `$id`, and read through `registry.contract(name)`. Prose never
  restates a schema, a version or a count.
- `docs/PRODUCT-STATE.md` records what is built. `docs/NEXT-SLICE.md` is the
  execution queue; completed work is removed from it rather than kept as queue
  history.
- Generated files belong to the generator that produces them, never to a hand
  edit.

Repository state is established from the tree and from executable contracts,
not from local notes, home-directory files or an executor's memory. Before
claiming repository state, establish it in the current shell:

```bash
pwd
git status --short --branch
git remote -v
git fetch --prune
git log -1 --oneline
```

Every shell command starts from its declared working directory; never assume a
`cd` from an earlier command persisted.

## Evidence

Evidence is ranked: observed runtime or test; machine-readable schema or
contract; primary vendor documentation; community documentation; blogs,
samples and issues.

Observation proves what happened, not what it means. A product conclusion also
needs the contract or the owner decision that defines its meaning. If evidence
cannot be obtained, record `not established` — never infer absence from an
observation that could not be made.

**A collector never turns a denial into an empty tenant.** Permission denied,
an unsupported surface and a licence that is not present are three different
answers, and none of them is a tenant with nothing in it.

## Gate

```bash
./tools/release-check.sh
```

That one script is the release-readiness contract, and a partial invocation is
not a release result. A red gate is current work until it is fixed or proven to
require an owner decision; do not dismiss it because another slice exposed it.
Once it is green, do not add redundant verification rounds.

After a release, `./tools/post-release-check.sh` proves the published artefact
installs from the public index and runs — a release that only built is not a
release that shipped.

Every commit carries `Signed-off-by` (`tools/dco-check.sh`).

## Language

This repository is public. Everything in it — code, comments, tests,
documentation, commit messages, branch names — is written in English.

## Search scope

Anchor every search at this repository's root. Not `~`, not a parent
directory, not "only to read the file names": a recursive read outside the
checkout opens whatever else happens to be on the machine, and the fact that
only paths reach the screen does not change what was read.

```bash
grep -r <pattern> .        # inside the repository
grep -r <pattern> ~/dev    # never
```

If a value is not in this repository, it does not exist for this work.
Widening a search until something matches is how an executor ends up reading
what nobody authorised, to answer a question whose honest answer was `not
established`.

## Execution model

Repository work is synchronous by default. A task is not complete until the
process that performs it has completed. Do not convert synchronous repository
work into asynchronous background work, and do not depend on temporary task
IDs, background logs or hidden runtime state. The observable result of the
command is part of the repository evidence.

Background execution is allowed only when the owner explicitly requests it or
when the task itself is to create a persistent service.

Do not write durable product state outside the repository. Temporary
directories, home-directory notes and scratch files are not evidence and do not
survive the person who made them.

## Decisions requiring explicit authorization

- publish a release, or change what a published contract means;
- change identity, consent, permissions or any tenant state — this engine
  reads, and acquires nothing;
- send external messages, or open upstream issues or pull requests;
- change licensing, product positioning or legal claims.

Normal work inside an already accepted slice needs no new authorization. A
repository boundary is not a stopping condition, but leave the repository
coherent and run the gate before switching away from it.

## Working rules

- Establish current behaviour from the running system, the code and the tests;
  establish intended behaviour from recorded decisions and the architecture.
  Documentation is evidence of intent, not proof of runtime behaviour.
- If two sources disagree and ownership does not settle which is stale, record
  the contradiction for the owner; do not silently choose.
- Deliver the requested scope without silently widening, narrowing or
  redesigning it.
- Preserve unrelated changes. Measure the affected set before a bulk edit, and
  check for a concurrent writer before a destructive one.
- Inspect licence terms before reusing external code or prose.
- An implementation change belongs where the semantic decision lives, even when
  something else first exposed the gap.
