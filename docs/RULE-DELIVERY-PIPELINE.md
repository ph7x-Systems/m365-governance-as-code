# Rule Delivery Pipeline

Owner: this repository. A rule, a collector and an evidence contract are
engine artefacts, so the order in which they are built is an engine decision
and is written here once.

## The sixteen stages

```text
 1  Microsoft documentation          authority, semantics, permission, limits
 2  Graph or API surface identified  the endpoint that answers it
 3  Endpoint verified in the API     it exists, in the version claimed
 4  Collector, evidence and rule     one vertical, never a rule alone
 5  Endpoint tested on a tenant      a real acquisition, refusals included
 6  Command line run on that tenant  the product path, not a side script
 7  Assessment and bundle verified   a canonical artefact with an identity
 8  A consumer opens it              COMPATIBILITY established
 9  Consumer workflows complete      a usable product
10  Visual and interaction quality   the pH7x bar, not a demo
11  Packaging, three platforms       customers can obtain and run it
12  Engine and consumer candidate    one coherent release, together
13  Regression on a clean machine    it works where nobody built it
14  Site derives from RELEASED work  never from a branch
15  Site publication gate
16  Publish
```

No stage is skipped. No stage is stopped at for a report. The site is never
edited by hand to announce a rule.

## The stage nobody may skip by accident

> **Do not advance the pipeline stage merely because the previous artefact can
> technically be opened.**
>
> Stage 8 proves compatibility.
> Stage 9 proves the consumer is a usable product.
> Stage 10 proves it meets the pH7x visual and interaction bar.
> Stage 11 proves customers can obtain and run it.
>
> Only after those three are green may release and website work resume.

THIS PARAGRAPH EXISTS BECAUSE THE MISTAKE WAS MADE. On 2026-08-24 a real
tenant run reached a consumer that opened twenty-seven runs and lost no
meaning, and the executor called that stage 9 and went looking at the site.
It was stage 8. "Twenty-seven runs opened and basis survived" is a statement
about a file format; a person cannot do their job with a file format.

The distance between the two is the whole product. `PRODUCT-OBSERVED 18` means
eighteen rules crossed the technical path that has been observed. It does not
mean eighteen rules a customer can act on, and reading it as the second is the
same inflation this engine already corrected once, when `full` was rendered as
READ FROM A TENANT, END TO END.

## Why the order is the contract and not a preference

Each stage answers a question the one before it cannot, and every shortcut this
repository has taken was a stage assumed rather than done.

**A reference page does not prove an endpoint exists in the version you named.**
`tools/graph-schema-check.py` puts every recorded Graph surface to the service's
own `$metadata`, which is why `admin/cloudLicensing/assignments` is written down
as beta rather than discovered as beta by somebody who built on it.

**An endpoint existing does not prove the fields arrive.** A response can return
`200` and be silently partial: several of the roles that grant
`crossTenantAccessPolicy` return basic properties only, excluding identity
synchronization settings. Nothing offline finds that. It is found by making the
call and looking at what came back.

**The API working does not prove the product works.** This is the shortcut that
costs most, because it is the most convincing: a script proves the endpoint, and
`m365-governance run` is assumed to do the same thing. It does not. The product
path is authentication, collection, coverage, evidence, assessment and bundle,
and each of those is code that can be wrong while the endpoint is right.

**Graph Explorer proves the API. The CLI proves the product. Neither
substitutes for the other.**

**A bundle existing does not prove a consumer can read it.** The stage is a
program that did not produce the artefact opening it and interpreting it. A
finding arrives carrying `basis`, `coverage`, `unknown`, provenance and
`limitation`, or those were lost somewhere between the rule and the reader —
and losing them is losing the product rather than losing a field.

Which consumers exist, and which of them is commercial, is not this
repository's question. What is published here is the artefact and the contract
it is written against, and any program holding that contract is a consumer.

## Three states, so that nobody counts the wrong thing

```text
IMPLEMENTED        code, contracts and deterministic tests
TENANT-OBSERVED    a real acquisition, from a real directory
PRODUCT-OBSERVED   CLI to bundle to consumer, on that same tenant
```

They are reported separately and they are never added together. `39 rules` is
one number; `16 have been run against a tenant` is another; and a catalogue that
publishes the first while implying the second is the artefact this product
exists to replace.

`tools/rule-readiness.py` measures all three. Its ladder is the same one in the
gate's own words: `RULE-READY` is IMPLEMENTED, `TENANT-PROVEN` is
TENANT-OBSERVED, `PRODUCT-PATH` is PRODUCT-OBSERVED.

## What a stage produces

| Stage | Establishes | Recorded in |
| --- | --- | --- |
| Documentation | authority, semantics, permission, `v1.0` or `beta`, known limits | the rule's `basis.sources`, and `candidate-surfaces.json` before the rule exists |
| API surface | the endpoint exists in the version claimed | `schema_check`, by `tools/graph-schema-check.py` |
| Endpoint observed | the fields arrive; `$select`, paging, 403, 404, 429; application against delegated | the collector's `validation` and `limitation` |
| Engine | collector, evidence and rule, as one vertical | the capability manifest and the rule file |
| Tenant | a real acquisition, with what was refused or partial | the capability's `proof.stages.acquisition` |
| CLI | the product path, not a side script | `proof.stages.evidence` and `assessment` |
| Bundle | a canonical artefact with its digest | `proof.stages.bundle` |
| Consumer | a program that did not produce it reads it without losing meaning | `proof.stages.consumer` |
| Site | the published product, derived | the site's vendored snapshot |

A `refused`, `partial` or `not-supported` result is a result. It is recorded at
the stage that found it and the family continues; it is never a failure to be
retried until it looks better.

## What the consumer stages require

Stage 8 is a format check and it is finished when a program that did not
produce the artefact opens it and nothing is lost. Stage 9 is a different
question with a different answer, and it is not reached by adding polish to
stage 8.

A consumer is a usable product when it carries, at minimum: an overview that
answers what happened; findings; what could not be established; inspection down
to the evidence; coverage; comparison; verification; workspaces and history;
search and filtering; unambiguous PASS, FAIL, UNKNOWN, REFUSED and PARTIAL;
light and dark; keyboard operation; empty, loading and error states that say
what to do next; a corrupt bundle and an incompatible contract handled as
answers rather than crashes; no temporary paths on screen; no fixture or demo
scaffolding; and no metric nobody can trace to the artefact.

Stage 10 is that product meeting the pH7x visual and interaction bar at 100,
125, 150 and 200 per cent, in small windows and large, with screenshots kept
as regressions.

Stage 11 is a clean install, run, and bundle opened on Windows x64, macOS arm64
and Linux x64.

None of the three is this repository's to build, and all three gate its
release, which is why they are named here rather than assumed.

## Where the site sits, and why it is last

The site vendors the engine's **published** revision. A rule that exists only on
a branch is absent from the public catalogue on purpose, and
`tools/refresh-governance-rules.py` in that repository names every rule in that
position each time it runs. Publishing a rule on a page before the engine that
implements it can be obtained would be announcing a product nobody can run.

## The order a family is built in, in one line

> Microsoft docs → API surface → endpoint observed → collector, evidence and
> rule → tenant acquisition → CLI on the same tenant → bundle → consumer →
> derived site refresh. Do not skip a stage, do not stop for an intermediate
> report, and do not update the site before the product is published.
