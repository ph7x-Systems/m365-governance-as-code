# Epic B: what one identity cannot see

**Opened 2026-08-07, on the `1.0.0-beta.1` baseline.**

Epic A proved the model carries a service end to end. Every number it produced
carries the same unspoken clause: *as far as this identity could see*. Six of
53 sites refused the collector outright, a group owner is one principal that
may be forty people, and a tenant that no longer exists cannot be collected
from at all.

Epic B is that clause. It is about the reach of the evidence rather than the
shape of it, which is why the model is frozen for the whole of it: if a slice
here needs the model to change, that is a finding about Epic A and it goes
through [CHANGE-POLICY.md](CHANGE-POLICY.md) with the evidence that motivated
it.

**Milestone A is closed and does not reopen.** See
[MILESTONE-A.md](MILESTONE-A.md).

---

## The slices, in order

Ordered by what unblocks the most downstream work, not by interest.

### B1. Application authentication

Every count in this repository is what one person can see. An app registration
with `Sites.Read.All` and admin consent removes the clause.

`identity_kind` already distinguishes `application`, `delegated` and
`imported`, and the field has only ever carried two of the three. This slice
is the first time the schema's own vocabulary is fully used.

**Closes when:** the collector authenticates as an application, the evidence
records `identity_kind: application`, a run against the validating tenant
enumerates sites the delegated run could not, and the difference between the
two runs is recorded rather than assumed. A rule reads it or no rule does; the
point of this slice is coverage, not a new claim.

**First, before anything else:** whether the six sites that returned
*Attempted to perform an unauthorized operation* become readable. If they do
not, the reason is the finding.

### B2. Group expansion

A site owner may be a group. The collector declares the expansion
`not-attempted` and emits a lower bound, the engine reasons over the bound
correctly, and nobody knows the number.

Turning bounds into counts is the whole slice, and it will make some findings
appear and some disappear. Both directions matter: a site with "at least 1
owner" that turns out to have 1 was under-reported, and one that turns out to
have 40 was over-reported as fragile.

**Depends on B1?** Not established. Directory reads may be reachable with
delegated scopes. That is a question to answer against the tenant before
sequencing, not to assume.

**Closes when:** expansion is attempted, partial expansion is still declared
partial, and SPO-SITE-001 produces exact counts where the group resolved and
bounds where it did not — in the same run, on different sites.

### B3. Importers and Assessment mode

The mode that answers a question about a tenant nobody can connect to: an
inventory exported from somewhere else, read as evidence.

`identity_kind: imported` exists for this. The governing sentence, already
written in [SCOPE.md](SCOPE.md), is that this project evaluates the Microsoft
365 tenant that exists today and does not infer the characteristics of a farm
that is not present. An importer does not weaken that: it says where the facts
came from and refuses to pretend they were observed.

**Closes when:** an import produces a document that passes the evidence schema
unchanged, provenance names the source file and the exporter, no fact imported
is ever marked `observed`, and a report renders the difference between an
imported run and a collected one without a reader having to look for it.

### B4. HTML reporting, refined

HTML exists and is self-contained. What it is not is designed. This slice is
about a reader who is not in a terminal and did not write the rules.

**Closes when:** the six outcomes are visually distinguishable without colour
alone, `unknown` cannot be mistaken for `pass` at a glance, the limitation and
the basis are as prominent as the finding, and a resource set aside by a
profile is visibly present rather than absent.

Nothing here touches the engine.

### B5. SARIF, after the `unknown` decision is made

**Not started until the representation of `unknown` is decided formally.**

What is verified, from the SARIF 2.1.0 schema itself rather than from prose:

`result.kind` permits exactly six values — `notApplicable`, `pass`, `fail`,
`review`, `open`, `informational`. `result.level` permits `none`, `note`,
`warning`, `error`.

Six outcomes and six kinds is a coincidence, not a mapping. Three are
immediate:

| ours | SARIF kind |
|---|---|
| `pass` | `pass` |
| `fail` | `fail` |
| `not-applicable` | `notApplicable` |

Three are the decision:

- **`unknown`** — `open` ("requires action before the scan is complete") reads
  closest to what it means: go and collect more. `review` is the alternative
  and says something different, that a person should look at a result the tool
  already has.
- **`invalid-evidence`** — plausibly `review`, since the fix is not more
  collection but a look at why the collector produced that.
- **`error`** — describes the engine and not the resource, so it is arguably
  not a `result` at all. SARIF carries tool failures in
  `invocation.toolExecutionNotifications`. Emitting it as a result would put a
  statement about our own code in a list of statements about a tenant, which
  is the one thing this model has refused everywhere else.

**To verify before writing any of it:** SARIF constrains which `kind` values
may carry a non-`none` `level`. Two readings of the specification prose
disagreed and the JSON schema does not encode the constraint, so it is
unverified. If a non-`fail` kind is forced to `level: none`, then an `unknown`
on a high-severity rule arrives in somebody's pipeline UI with no severity at
all — which is `unknown` quietly reading as fine, in a format we chose. That
would be a reason to reconsider the slice, not a detail to work around.

---

## Not in Epic B

- **More SharePoint rules.** They are welcome and they are not an epic. A rule
  is a pull request against a frozen model.
- **A second service.** Exchange, Teams or Entra is Epic C, and it is the real
  test of whether the evidence schema is service-agnostic. Doing it inside B
  would confuse "we could not see it" with "we have not modelled it".
- **Anything that changes a tenant.** Not in any epic, ever.

---

## Carried debt

### CI: two gates ride on one matrix entry

`Coverage` and `Collector is read-only` run only on the 3.13 entry, so for
those two checks a matrix of three has the availability of a matrix of one.

On 2026-08-06 that is exactly what happened: three runs were cancelled at
15m01s with zero steps executed, no runner having picked them up, and when the
incident eased 3.11 and 3.12 passed while 3.13 did not — leaving precisely
those two gates unproven. They passed on the following attempt with no change
to the repository.

**Registered as debt and deliberately not fixed.** What was observed was
runner availability, not a defect in the design. It is revisited if it recurs
often enough to be a pattern rather than an incident; the fix is a choice
between running both gates on every entry, at three times the cost, and logic
that `if:` does not express.
