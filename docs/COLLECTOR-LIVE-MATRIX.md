# Collector live-validation matrix

**Every collector is proved against a tenant, not only against fixtures.**
Offline tests close the logic; a run closes the integration. A collector with
green tests and no live run has been proved to behave as somebody believed the
API behaves.

> **No collector counts as closed on offline tests alone.** Each one needs a
> positive live proof against the test tenant, and where it makes sense a
> negative live proof with a limited identity.

The tenant is not named here: this repository is public.

## State vocabulary

| State | Means |
|---|---|
| `not live-validated` | offline tests only |
| `negative path validated` | a typed refusal was observed, no successful read |
| `live-validated` | a real read produced real evidence |
| `fully live-validated` | both, for the paths this tenant can exercise |

## The matrix

Recorded 2026-08-17 unless stated. `n.a.` means the surface has no pagination
to exercise.

| Collector | Offline | Live + | Live − | Pagination | Rules it supports | Status |
|---|---|---|---|---|---|---|
| `sites` | ✓ | `partial`, 11 docs | `failed` under `AllSites.Read` | none at 11 items | `SPO-LIST-001/002/003`, `SPO-SITE-003` | **fully live-validated** |
| `owners` | ✓ | `completed`, 1 doc | — | n.a. | `SPO-SITE-001`, `SPO-SITE-002` | **live-validated** |
| `modernity` | ✓ | `completed`, `pages` + `web` | — | n.a. | `SPO-MODERN-001/003/004` | **live-validated** |
| `classification` | ✓ | `completed` | — | n.a. | `SPO-CLASS-001/002/003` | **live-validated** |
| `sharing` | ✓ | `completed` | — | n.a. | `SPO-SHARE-001/002/005` | **live-validated** |
| `activity` | ✓ | `completed` | — | n.a. | `SPO-ACTIVITY-001` | **live-validated** |
| `permissions` | ✓ | `completed`, 17 docs | — | n.a. | `SPO-LIST-001/002/003`, `SPO-SITE-003` | **live-validated** |
| `agents` | ✓ | 0 agents, 2026-08-10 | — | n.a. | **none**, by decision | **live-validated** |
| `tenant-sharing` | ✓ | 3 properties, 2026-08-08 | — | n.a. | `SPO-SHARE-003`, `SPO-SHARE-004` | **live-validated** |
| `spfx` | ✓ | not observed | `403 Forbidden`, 2026-08-08 | n.a. | `SPO-SPFX-001` | **negative path validated** |
| `conditional-access` | ✓ | 10 policies, 1 location, defaults — **read by the provider, not by the slice** | `403` without `Policy.Read.All` | none at 10 items | **none**, by decision | **provider live-validated, slice not live-validated** |

### What this table answers immediately

**Is this collector ready for production?** The Status column.

**Which rules depend on it?** The rules column. `agents` is the deliberate
exception: it produces an inventory that no rule reads, because Microsoft
publishes no normative position on how many agents an organisation should have,
and `consumed_by` names the report instead.

**If it fails, what becomes `unknown`?** The rules in its row. `SPO-SPFX-001`
is the live case: `spfx` has never returned data from this tenant, so that rule
has never been evaluated against real evidence and would answer `unknown` for
every site if run today.

## What the evaluations produced, which is the other half of the proof

A collector that reads is not a collector that produces a governance answer.
Every document above was evaluated against its own profile:

| Collector | Outcomes |
|---|---|
| `owners` | 1 `fail`, 1 `unknown` |
| `modernity` | 3 `pass` |
| `classification` | 2 `fail`, 11 `unknown`, 2 `not-applicable` |
| `sharing` | 1 `pass`, 2 `not-applicable` |
| `activity` | 1 `pass` |
| `permissions` | 13 `pass`, 34 `unknown`, 4 `not-applicable` |

**`unknown` outnumbers `pass` on two of the six**, and that is the product
working rather than failing: a rule that cannot decide from what was read says
so instead of passing. A run that had returned green everywhere would be the
result worth distrusting.

**Ten of eleven now have a positive live read.** `spfx` has only the negative
path, refused by the tenant in August with `403 Forbidden`, and that refusal is
itself a valid row.

Before this file existed, five collectors had never been read from a tenant at
all and nobody could say which five.

## What `sites` proved, and it is the pair that matters

The same collector, the same tenant, two identities:

```text
AllSites.Read       ->  failed,  0 artefacts, observed: null, manifest still written
AllSites.FullControl ->  partial, 11 artefacts, coverage naming the gap
```

**Neither produced `completed` and neither produced an empty estate.** The
`partial` carries the collector's own sentence: eleven sites enumerated by a
delegated identity, and the ones it cannot see are absent from the run with
their number not knowable from there.

## Defects only a live run found

### 1. `--output` accepts a directory for a slice that writes one file

`collect owners --output <directory>` fails with a raw PowerShell error:

```text
Clear-Content is only supported on files.
```

Slices that read many resources write into a directory; slices that read one
write a file. **The CLI accepts either for every slice and the mismatch
surfaces as an internal error from another language.** A person reading that
line has no way to know they passed the wrong kind of path.

The engine already knows which slices are which: `Slice.needs_site` is a good
proxy and `shaped_like` is exact. This should be a typed refusal before the
process starts, not a `Set-Content` failure four seconds in.

**Fixed.** `Slice.writes_many` declares which slices read many resources, and
`collect` refuses the wrong kind of path before starting the process, naming
what to pass instead. Two slices write many — `sites` and `permissions` — and a
test freezes that set so the refusal is a property of the contract rather than
a heuristic over a name.

### 2. Live validation costs one interactive sign-in per collector

Each `collect` invocation spawns its own PowerShell process and authenticates
again. Validating ten collectors means ten browser prompts for the tenant
owner, which is the most expensive resource in this process and the reason
this matrix is being filled one row at a time rather than in a loop.

There is no way today to open one session and drive several slices through it.
That is a real gap in the collector's design for live validation, and it is
recorded here because it shapes how long this matrix takes to close.

## The maturity gate

**This file is a gate, not a photograph of one slice.** A collector's row is
what says whether it may be relied on, and a row that does not exist is an
answer too.

> **No new collector enters this repository without:**
>
> - complete offline tests, covering the whole answer matrix;
> - a row in this file;
> - a positive live proof, or an explicit `needs-tenant-validation` with the
>   reason it could not be obtained;
> - the list of rules it supports, or a statement that it supports none and
>   why.

**No rule depends on a collector that has only been simulated.** A collector at
`not live-validated` may ship evidence and may be evaluated; a rule written on
its output is a governance conclusion resting on a belief about an API.

## The three outstanding gaps, ranked

### 1. One interactive sign-in per collector — the one that does not scale

Each `collect` spawns its own process and authenticates again. Six collectors
were proved here at the cost of six browser prompts. At thirty or forty
collectors, live validation stops being something anybody does.

**Live validation should open one authenticated session and drive every
compatible collector through it.** The collector authenticates inside
`Get-SpoEvidence.ps1`, so this is an engine change rather than a script a
caller can write, and it is the highest-value of the three.

### 2. Real pagination, never exercised

The only gap that spans every collector. Eleven sites and ten policies produced
no next link, so the client's paging is proved offline and unproved live. It
does not block shipping; it stays unproved until a tenant large enough exists.

### 3. `spfx` has no positive path

**Not a defect in the collector.** The tenant refused the API permission in
August, so the surface has never returned data here. It is correctly
`needs-tenant-validation`, and `SPO-SPFX-001` is the one rule in the product
whose supporting collector has never returned real evidence.

### 4. The `conditional-access` slice has not itself been run against a tenant

**The provider has, and that is a different claim.** The Graph reader read ten
policies, one named location and the Security Defaults state from the test
tenant, and was refused with `403` by an identity without `Policy.Read.All`.
What has not run live is the CLI slice above it: the evidence documents, the
coverage carried whole into each one, the refusal document and the collection
manifest are proved offline, against every answer in the matrix, and have never
been produced from a real read.

The gap is a token, not a design: the slice spends one somebody already holds,
and obtaining it costs the tenant owner an interactive sign-in — gap 1 again,
in its Graph form. The row says `slice not live-validated` until that run
happens, and no rule is written on this evidence in the meantime.
