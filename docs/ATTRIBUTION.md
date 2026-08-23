# Loss of attribution across a composition boundary

**A defect class, named because it has now appeared twice and the second time
nobody recognised it as the first.**

## The class

> **When a layer combines several inputs into one structure and does not keep
> which input supplied which part, every question downstream that needs the
> origin becomes unanswerable — and stays unanswerable in a way that looks like
> a missing feature rather than like discarded information.**

It is not a SharePoint problem, not a Conditional Access problem and not a
proof-registry problem. Those are three places it has surfaced.

**What makes it hard to see** is that nothing fails. The composed structure is
correct for the question the composition was built to answer, every test over
that question passes, and the loss is only visible to somebody asking a
question nobody had asked yet. By then the layer looks settled.

## Where it has appeared

**1 · Conditional Access evidence.** Each policy was published as one fact
holding the whole Graph object. The composition there is inside a single fact:
`state`, `displayName`, `grantControls` and the rest combined into one value
with no addressable parts. The consequence was total — no rule could be written
against the family at all, and the reason was read for weeks as an editorial
decision not to write one. Fixed by publishing the fields a rule needs beside
the untouched object.

**2 · Evidence documents composed by resource.** Two collectors describing one
site produce two documents, and `composing.compose` unions their facts into
one. The consequence surfaced while wiring the proof registry: a run cannot
record that a rule decided something from a given acquisition's facts.

**3 · And the second one is worse than "unavailable".** `_facts()` builds
`source[name] = where` as it unions — **it already knows exactly which document
supplied each fact block** — and drops that table when it returns. The composed
document then carries `documents[0]`'s provenance for every fact in it. So a
fact acquired by the sharing collector is presented under the owners
collector's provenance. **This is not missing information. It is computed,
discarded, and then contradicted.**

## The relation that must survive composition

Not *assessment belongs to collector*. A rule may read facts supplied by
several acquisitions, and inventing a one-to-one ownership to make a gate green
would be a second authority — the thing this product exists to remove.

The relation is one level lower and it already exists:

```text
fact block  ->  the evidence document that supplied it
```

Everything else is derived from it, mechanically, and from artefacts that are
already persisted:

```text
finding
  -> result.evidence_used[].path            "permissions.unique_scope_count"
  -> the first segment of that path         "permissions"
  -> attribution[fact block]                the document that supplied it
  -> that document's provenance             the acquisition
```

**Nothing in that chain is a filename, a slice naming convention, a collector
identity string, a regular expression, an execution order, or a sentence read
out of the human report.** Each step is a lookup in a structure the artefact
already carries or is about to.

**It survives the case that kills every name-based approach.** Eleven
SharePoint slices all publish `provenance.collector = "spo-collector"`. The
attribution is to the DOCUMENT, not to the collector's name, so two acquisitions
sharing an identity string remain distinct. A document therefore needs a stable
identity of its own, and the honest one is a digest over its canonical bytes —
which the engine already computes for every artefact it publishes.

## The eight cases the contract must distinguish

Written before any schema changes, because a schema chosen first decides which
cases exist.

| | Case | What must be representable |
|---|---|---|
| 1 | A rule depends on ONE acquisition | The chain resolves to one document, and says so |
| 2 | A rule depends on TWO acquisitions | The chain resolves to both, listed. **No ownership invented, no first-wins** |
| 3 | Two slices share a collector identity | The two remain distinct, because attribution is to the document and not to the name it published |
| 4 | Evidence collected, no rule consumed it | Acquired, entered evaluation, **not consumed** — and that is a third state, distinct from not acquired and from consumed |
| 5 | Rules ran over composed evidence carrying no attribution | `attribution unavailable`, explicitly. **Never `proven` by inference**, and never silently absent |
| 6 | Acquisition partial or refused, conclusion `unknown` | The `unknown` resolves to the acquisition that tried, so a reader learns WHY it is unknown rather than only that it is |
| 7 | Zero rules ran | No chain to prove. `assessment: not-attempted`, and it is not a failure |
| 8 | The human report explains more than the machine-readable artefact | **A GAP, recorded as one, and never proof.** Anything the report asserts that cannot be reconstructed from the artefacts is a defect in the artefacts |

Case 8 is not a data structure. It is a test, and it is the one that keeps the
rest honest: *software establishes, people decide* applies to this software
too, and a person must not have to reconstruct by hand a relation the run
claims as `proven`.

## Where the attribution belongs

**On the assessment, not on the composed document**, and the reason is whose
question it answers.

The composed document is transient: built for evaluation, never published,
never held by anybody. The assessment is the artefact a consumer receives, it
already carries the ORIGINAL documents each with its own provenance, and the
question *which observation supports this finding* is a consumer's question
asked of the artefact in their hand, long after every process has exited.

So the composition computes the table it already computes, passes it up, and
the assessment publishes it. A consumer walks the chain with no engine, no
collector, and no knowledge of how either works.

## What `assessment: proven` may mean, and it was five things

The proof registry's `assessment` stage was raised on one condition and could
have been read as any of these:

1. an assessment document exists;
2. it derives from this run;
3. rules were evaluated over evidence that included this acquisition's facts;
4. at least one rule reached a conclusion FROM this acquisition's facts;
5. every conclusion in it has a reconstructible chain back to an observation.

**Those are five different claims and aggregating them is the shape this
product refuses in other people's tools.** A single word covering all five is
the ambiguous green box, published about ourselves.

It is defined as (4), with (5) as the condition that makes (4) checkable:

> `assessment: proven` — at least one rule reached a conclusion that is not
> `unknown` and not `invalid_evidence`, from at least one fact block this
> acquisition supplied, **and the chain from that conclusion back to this
> acquisition is reconstructible from the persisted artefacts alone.**

And what it does not mean, published beside it: that every conclusion in the
assessment has such a chain, that the conclusions are correct, or that anything
about the tenant was proved. It means a rule consumed what this acquisition
produced, and that a reader can check that claim without being told.

## The gate this closes with

From the persisted artefacts, without reading prose from the human report:

```text
what was attempted
  -> what was acquired
  -> what evidence entered evaluation
  -> what rules evaluated it
  -> what conclusions resulted
  -> what cannot be proven
```

Any link that does not exist is stated by the document rather than left for a
reader to notice. And the acceptance is specific: **take a canonical workspace,
pick one finding, and walk mechanically from it to the observations that
support it — without the human report, and without knowing how the collector is
implemented.**

Until that runs, `proven` does not deserve the name.
