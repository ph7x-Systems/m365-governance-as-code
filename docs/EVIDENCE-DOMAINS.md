# The evidence coverage matrix

**This engine governs Microsoft 365, and it can observe some of it.** Those are
two sentences and the difference between them is this document.

The canonical matrix is not written here. It is published by
`m365-governance capabilities --domains`, and as `domains` in
`capability-manifest/1.2.0`, derived from the domain catalogue in
`src/m365_governance/domains.py` and the slices that name each domain. Nothing
below is a second copy of it: what is written here is the rule the matrix
obeys.

## Why a catalogue of collectors is not a map

A list built from what exists answers *what did we write*. Every entry in it
works, so it reads as competence, and a reader who does not already know the
product concludes it covers Microsoft 365. Ten SharePoint capabilities and no
mention of Exchange is a true list and a false picture.

So the matrix names **every domain this engine claims**, whether or not it can
observe it, each with the question it answers or fails to answer. The domains
carrying no acquisition surface are the entries that make the document honest.

`not-started` is not a weaker `none`:

| State | Means |
| --- | --- |
| `not-started` | there is no acquisition surface here at all |
| `none` | a collector exists and has only ever run offline |
| `negative-only` | it ran against a real tenant and the branch that reports a finding was never taken |
| `provider-only` | the transport underneath read a real tenant, this slice's own path did not |
| `partial` | this slice's own path read a real tenant for some of its areas and never ran for the others |
| `full` | the path that produces this evidence was observed against a real tenant |

## The contract every domain obeys

> **Acquisition surface → population → acquisition method → coverage →
> provenance → limitations → rules only where authority exists.**

Read as a sequence of refusals rather than a checklist, because each step is
one:

- **Acquisition surface.** What is read, in Microsoft's terms. Named for
  unstarted domains too: a surface nobody has looked for is a different kind of
  absent from one that does not exist.
- **Population.** What the read enumerated, and what it could not. An inventory
  surface defines a population; it does not define existence outside that
  population.
- **Acquisition method.** `enumerated` or `queried`, because *this query
  returned zero* and *this enumerated population is empty* are different facts.
- **Coverage.** Which areas completed, which did not, and whose limitation each
  absence is: the implementation, the tenant or identity, Microsoft, or the
  caller. Only the first is unfinished product.
- **Provenance.** How the document knows which tenant it is about, and how the
  session was established.
- **Limitations.** What the evidence cannot support, stated in the evidence.
- **Rules only where authority exists.** A conclusion needs a sentence somebody
  can defend. Where Microsoft publishes no normative position, the domain
  collects and decides nothing, and says so in `withholds`.

## The entry rule

> **No domain enters as supported.** It arrives at `not-started`, gains a
> surface at `none`, and moves through `provider-only`, `partial` and `full` as
> live proof arrives.

There is no field anywhere that says a domain is supported, and
`tests/test_domains.py` fails if one appears. The rule is written down because
the inflation it prevents has happened three times on single slices: `spfx`
published `live-validated` for a branch no real catalog ever produced,
`licensing` was one commit from publishing a state that was false, and
`conditional-access` counted a transport read as a slice read.

A domain never carries a state of its own beyond `not-started`. An aggregate
over unlike observations is the artefact charter `D5` refuses: a domain holding
one proven surface and one unproven one is not half-proven. What it publishes
instead is the state of its **least proved surface** — a fact about a
particular surface — and a count per state.

## Live acquisition is separately authorized

Installing or configuring an authentication dependency is not authorization to
authenticate. Any operation that establishes a session against a real directory
or tenant needs explicit authorization for that operation, asked immediately
before it and never inferred from a nearby instruction. One consent does not
extend to the next operation, to a second run, or to a different scope; a
session that already exists is not permission to use it.

This belongs beside the matrix because the matrix is what creates the pressure:
every state above `none` requires a live run, and a coverage table is exactly
the kind of document that makes reaching for one feel procedural.
