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

| Collector | Positive | Negative | Pagination | Schema | State |
|---|---|---|---|---|---|
| `sites` | `partial`, 11 documents | `failed` under `AllSites.Read` | none at 11 items | 11/11 valid | **fully live-validated** |
| `owners` | `completed`, 1 document | not attempted | n.a. | valid | **live-validated** |
| `modernity` | `completed`, `pages` + `web` | not attempted | n.a. | valid | **live-validated** |
| `classification` | `completed` | not attempted | n.a. | valid | **live-validated** |
| `sharing` | `completed` | not attempted | n.a. | valid | **live-validated** |
| `activity` | `completed` | not attempted | n.a. | valid | **live-validated** |
| `permissions` | `completed`, 17 documents | not attempted | n.a. | 17/17 valid | **live-validated** |
| `agents` | 0 agents returned, 2026-08-10 | not attempted | n.a. | recorded | **live-validated** |
| `tenant-sharing` | 3 properties read, 2026-08-08 | not attempted | n.a. | recorded | **live-validated** |
| `spfx` | not observed | `403 Forbidden`, 2026-08-08 | n.a. | — | **negative path validated** |
| `conditional-access` | 10 policies, 1 named location, defaults read | `403` without `Policy.Read.All` | none at 10 items | provider only | **fully live-validated** at the provider |

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

Queued rather than fixed here: it belongs to the CLI's argument contract.

### 2. Live validation costs one interactive sign-in per collector

Each `collect` invocation spawns its own PowerShell process and authenticates
again. Validating ten collectors means ten browser prompts for the tenant
owner, which is the most expensive resource in this process and the reason
this matrix is being filled one row at a time rather than in a loop.

There is no way today to open one session and drive several slices through it.
That is a real gap in the collector's design for live validation, and it is
recorded here because it shapes how long this matrix takes to close.

## Rule

**No rule depends on a collector that has only been simulated.** A collector at
`not live-validated` may ship evidence and may be evaluated; a rule written on
its output is a governance conclusion resting on a belief about an API.
