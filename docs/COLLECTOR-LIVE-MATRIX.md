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
| `owners` | `completed`, 1 document, rules decided | not attempted | n.a. | valid | **live-validated** |
| `agents` | 0 agents returned, 2026-08-10 | not attempted | n.a. | recorded | **live-validated** |
| `tenant-sharing` | 3 properties read, 2026-08-08 | not attempted | n.a. | recorded | **live-validated** |
| `spfx` | not observed | `403 Forbidden`, 2026-08-08 | n.a. | — | **negative path validated** |
| `modernity` | not observed | not observed | — | — | `not live-validated` |
| `sharing` | not observed | not observed | — | — | `not live-validated` |
| `activity` | not observed | not observed | — | — | `not live-validated` |
| `classification` | not observed | not observed | — | — | `not live-validated` |
| `permissions` | not observed | not observed | — | — | `not live-validated` |
| `conditional-access` | 10 policies, 1 named location, defaults read | `403` under an identity without `Policy.Read.All` | none at 10 items | provider only | **fully live-validated** at the provider |

**Four of eleven are fully or partly proved. Five have never been read from a
tenant at all**, and until this file existed nobody could say which.

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
