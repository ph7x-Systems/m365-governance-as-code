# Rule Delivery Pipeline

Owner: this repository. A rule, a collector and an evidence contract are
engine artefacts, so the order in which they are built is an engine decision
and is written here once.

## The rule

**Microsoft documentation → API surface → endpoint observed → collector,
evidence and rule together → tenant acquisition → CLI against the same tenant →
bundle → consumer → site.**

No stage is skipped. No stage is stopped at for a report. The site is never
edited by hand to announce a rule.

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
