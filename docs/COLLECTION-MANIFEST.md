# Collection manifest

## 1. Purpose

This document defines what a collection says about itself, and where it says
it. It is the other half of [EVIDENCE-SCHEMA.md](EVIDENCE-SCHEMA.md): evidence
declares what was observed about a resource, and a manifest declares what the
collection that produced it managed to do.

> **The manifest describes the collection. The documents describe evidence.**

Everything below follows from that sentence.

---

## 2. Why it is a separate document

An evidence document is about one resource. A collection is a batch. Putting
the state of the batch inside each document would write one truth once per
document, and it would leave the case this contract exists for unanswerable:

> **A collection that stopped halfway has to say what it did not read, and the
> documents that would have carried that sentence are exactly the ones that
> were never written.**

There is a second reason, and it is about who owns what. Execution metadata —
how long the collector ran, what exit code it returned, whether somebody
pressed Ctrl-C — does not belong to a resource. A document that carried it
would be describing a site and a process in one shape.

## 3. What it replaced

Nothing. Before this contract the only account of a collection was a process
exit code, and a consumer reading it could not tell a run that reached two
hundred of three hundred sites from one that never authenticated:

```python
@dataclass
class Outcome:
    slice_name, returncode, seconds, written, stdout, stderr

    @property
    def ok(self) -> bool:
        return self.returncode == 0
```

That collapse is made nowhere else here. Coverage keeps `requested` and
`completed` apart and names why a fact was unavailable; a rule answers
`unknown` rather than failing when the gap could change its answer. The
collection outcome was the one place a partial result and a failure were the
same value, and the only thing that could have separated them lived in a
process that had already exited.

---

## 4. The four states

| State | Means |
|---|---|
| `completed` | Everything the slice asked for |
| `partial` | Usable evidence, incomplete coverage, with the reason |
| `failed` | No usable artefact |
| `cancelled` | Stopped deliberately, and what was written is kept |

**`partial` is not a failure.** A collection that reached half a tenant
produced evidence worth exactly half a tenant, and that is a result. `collect`
exits `0` on a partial collection and says so in words, because an exit code
that called it a failure would push every caller back into guessing.

**`cancelled` is never inferred.** A collector killed by the network and one
stopped by a person exit identically. Only the caller knows which happened, so
only the caller sets it.

**The state is computed once, from facts.** Cancellation wins; then a non-zero
exit is `partial` where documents were written and `failed` where none were;
then a clean exit is `partial` where any document read less than it asked for.

---

## 5. Where it is written, and what it is called

`collection-manifest.json`, in the directory the evidence was written to. The
documented layout gives each slice its own directory, so that is the ordinary
case.

**A second collection in the same directory never replaces the first one's
account.** It carries its own short identity in the filename instead:

```text
evidence/sites/collection-manifest.json
evidence/sites/collection-manifest.4f2a91c0e7b3.json
```

Overwriting would destroy the only record that the earlier collection was
partial. The evidence it wrote would still be there, and evidence describes a
resource rather than a batch, so nothing would be left to say so.

Consumers glob `collection-manifest*.json`.

**A manifest is not evidence.** It is a `.json` file among the documents it
describes, and both directions of that mistake are closed: the collector's own
file listing does not count it as something it wrote, and `evaluate` does not
hand it to the evaluator.

---

## 6. What it carries

| Member | From | Note |
|---|---|---|
| `collection_id` | the digest | Identity derived from content, so a recipient can recompute it |
| `state` | computed | The four words above |
| `because` | facts | Never empty. A verdict with nothing behind it is what this product exists to stop shipping |
| `slice` | the invocation | Name, collector mode, what it reads, and the profile that consumes it |
| `started_at` / `finished_at` | wall clock | Compared against a tenant's own change history |
| `seconds` | monotonic clock | Kept separately, because a clock adjustment mid-collection makes the subtraction wrong |
| `exit_code` | the process | Published raw, and consumed as a verdict by nobody |
| `requested` | the invocation | The addresses it was pointed at. The half that survives a total failure |
| `observed` | the artefacts | The tenant the evidence says it is about, or null |
| `identity` | the artefacts | Which kind of identity looked, the client id, whether device code was used |
| `versions` | engine, bundle, artefacts | Engine, contract, and the collector's own version |
| `coverage` | the artefacts | A union by area name, and never a count |
| `artefacts` | disk | Path, digest, size, and whether it parsed |
| `digest` | computed | Over everything above |

**Nothing here is inferred from the exit code.** The tenant, the identity kind,
the collector version and the coverage all come from documents that were
actually written, and are null or empty where none were. A collection that
failed says `observed: null` and `identity.kind: not-established`, which is the
honest value: nobody read it.

### 6.1 Coverage is a union, not a total

The evidence's own `coverage` definition, referenced rather than restated, so
one definition moves at a time.

**An area is `completed` only where every artefact that asked for it read it.**
One document reading an area another could not is not the collection having got
all of it, and reporting it as complete would be the rounding-up the states
exist to stop.

There are no counts. A total computed here would be a second authority on how
much of a tenant was seen, agreeing with the documents until the day it did
not.

### 6.2 The artefacts are named, not restated

Each entry carries the path, a digest over the bytes, the size, and whether the
engine could parse it back as evidence. It does not copy the document's
coverage, provenance or facts: that would be one truth in two places waiting to
disagree.

`readable: false` is a reason to doubt the collection rather than a file to skip
quietly, and it always has a matching sentence in `because`.

### 6.3 What the digest proves, and what it does not

It proves that the manifest and the documents it names are the bytes that were
written, so a truncated transfer or an edited file is detectable.

**It proves nothing about who produced them.** Anybody who can edit the
manifest can recompute the digest. Authenticity is a signature, and this engine
does not claim one.

The canonical form is part of the contract: keys sorted, no whitespace between
tokens, UTF-8 with nothing escaped that does not have to be. It lives in
`m365_governance/canonical.py` and the assessment uses the same one.

---

## 7. What a consumer may conclude from silence

**Nothing.** Evidence collected before this contract existed, or exported from
somewhere else, carries no manifest. A consumer that finds none has learned
that nobody said — never that everything was read.

`evaluate` is conservative in exactly that way. Where manifests exist it states
the bound before the results, on stderr so a pipeline reading JSON on stdout is
unaffected. Where none exist it says nothing at all.

```console
$ m365-governance evaluate --evidence ./evidence/sites/
1 collections produced this evidence, 1 of them incomplete. What follows is
bounded by what was read:
  sites: partial
    the collector exited 1
    2 evidence documents were written
    contoso.json: owners not read (owners: permission-denied)
```

---

## 8. What is not here yet

**The assessment does not carry the collection state.** An assessment keeps the
evidence whole, including each document's own coverage, and it does not record
which collection produced it or in what state that collection ended. Carrying
it costs an assessment contract version, and it is the next step rather than
this one.

Until then, a manifest travels beside the evidence and not inside the
assessment, and a recipient who is sent only an assessment is not being told
whether the collection behind it was complete.
