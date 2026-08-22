# Live validation

**What it means for a capability in this engine to be called live-validated,
and what it does not mean.**

The per-capability state is published in the capability manifest and by
`m365-governance capabilities`. This document defines the vocabulary those
values come from. **It is not a log of anybody's runs**: which tenant was read,
when, and by whom is an operator's own record and does not belong in a source
tree.

## The states

| State | What was observed |
|---|---|
| `none` | offline tests only. The collector behaves as somebody believed the API behaves |
| `negative-only` | it ran against a real tenant and the surface was absent or empty. That it reports nothing correctly is proved; that it reports something correctly is not |
| `provider-only` | the transport underneath it read a real tenant; this slice's own path did not |
| `partial` | this slice's own path read a real tenant for some of the areas it covers, and never ran for the others |
| `full` | the path that produces this evidence was observed against a real tenant |

## Live-validated is a progression, not a boolean

**A real acquisition proves the acquisition path. It does not prove that the
interpretation of what came back is correct.** Those are different claims, and
a collector can satisfy the first while failing the second: a field can arrive
from a real tenant and still be summed into a figure that means nothing, or
change its JSON type with how much the collector found.

So a capability moves through five things:

| Step | The question it answers |
|---|---|
| **acquisition proven** | did a real acquisition execute and return evidence? |
| **representation checked** | was the evidence checked against what the product claims the fields mean? |
| **independent comparison** | was a second authoritative surface used, where one exists? |
| **divergence investigated** | where two surfaces disagreed, was it explained rather than silently resolved? |
| **live-validated** | only after the applicable steps are complete |

## What counts as a second surface

**Not another client reading the same property.** A PowerShell cmdlet wrapping
a REST call, an administration portal rendering a value, or a second product
surface documented as *following* a setting are all consumers of one authority,
and their agreement establishes nothing. **A consumer of a value is not a
second authority for it.**

A genuine comparison needs two representations the vendor maintains separately,
and it is made **only on the claims both actually establish** — a property
present in one and absent from the other is not a disagreement.

**Where only one authoritative surface exists, that is recorded**, and the
capability keeps the limitation. Manufacturing a comparison to complete a table
is the same failure as manufacturing a rule to justify a collector.

## What a representation check is

Reading the same field twice is not one. A setting that claims an effect is
checked **against the effect**: if a tenant setting says a report will not name
anybody, the check is reading such a report and seeing whether it names
anybody. One surface predicts, another observes.

## Where two surfaces legitimately disagree

Two values describing what looks like one fact can both be correct when they
come from different pipelines with different freshness — a live read of a
resource and an aggregation published hours behind it, over a window somebody
asked for, are not the same observation. **The comparison establishes what each
value means rather than which one wins**, and a product that picks one and
calls it the answer has discarded the more useful fact.

And a neighbouring surface may describe a different claim entirely. Two roles
with similar names, granted by different systems with different consequences,
do not corroborate each other, and recording their agreement as a cross-check
would be worse than recording nothing.
