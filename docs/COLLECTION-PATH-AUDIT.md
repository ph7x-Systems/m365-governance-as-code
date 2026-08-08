# Collection path audit

**Sharing and storage, audited 2026-08-08.**

A rule can be logically perfect and still be wrong, because the evidence it
reads was never valid. This audit follows the chain backwards for one domain:

```
property → collector → evidence → rule
```

It exists because writing a rule on `AnonymousLinkExpirationInDays` led to a
question about the property and ended in a question about the collector, which
is the more serious of the two.

---

## The rule this audit produced

> **Never build a rule on a property until the collection path is proven to
> populate it.**

A property that appears in an evidence envelope looks like a measurement. If
the call that produced it can return a default instead of the stored value,
then the envelope is asserting something nobody observed, and every rule
downstream inherits that.

## What started it

Microsoft documents this on `Get-SPOSite`
([reference](https://learn.microsoft.com/powershell/module/microsoft.online.sharepoint.powershell/get-sposite?view=sharepoint-ps),
checked on 8 August 2026):

> *If the Limit or Filter parameters are provided then the following site
> collection properties will not be populated and may contain a default value:
> … AnonymousLinkExpirationInDays, … DefaultLinkPermission, …
> OverrideTenantAnonymousLinkExpirationPolicy, … SharingCapability …*

`Get-SpoEvidence.ps1` reads sites two ways. One asks for a single site by
identity; the other enumerates. The question is whether anything a rule
evaluates comes from the second.

## The audit

| Evidence path | Collector call | Guaranteed populated | Read by | Verdict |
|---|---|---|---|---|
| `sharing.capability` | `Get-PnPTenantSite -Identity` | yes, one site per call | `SPO-SHARE-001` | **safe** |
| `sharing.effective_default_link_type` | `Get-PnPTenantSite -Identity` | yes | `SPO-SHARE-002` | **safe** |
| `sharing.default_link_permission` | `Get-PnPTenantSite -Identity` | yes | nothing | collected, unused |
| `sharing.anonymous_link_expiry_days` | `Get-PnPTenantSite -Identity` | yes | nothing | collected, uninterpretable, see below |
| `site.storage_quota_mb` | `Get-PnPTenantSite` (enumeration) | **unproven** | `SPO-SITE-003` | **safe by design**, see below |
| `site.storage_used_mb` | enumeration | **unproven** | `SPO-SITE-003` | **safe by design** |
| `site.storage_used_percent` | derived | only when both are `observed` | `SPO-SITE-003` | **safe by design** |
| `site.sharing_capability` | enumeration | **unproven** | nothing | **exposed, not safe to evaluate** |

### Why SPO-SITE-003 is safe

It reads three values produced by the enumeration path, and it survives an
unpopulated default because three defences already exist and are independent:

1. `applicability: site.storage_quota_mb > 0`. A quota that came back as a
   zero default puts the site **out of scope** rather than into a finding.
2. `evidence_requirements` marks all three paths `required: true`. Without
   them the rule does not evaluate at all.
3. The percentage is derived only when used **and** quota are both `observed`
   and the quota is above zero. Otherwise it is written as `missing`, with the
   reason already in the collector: *a percentage of a quota nobody returned
   would be a number with no denominator, which is worse than not having it.*

An unpopulated value therefore becomes *out of scope* or *missing*, never
`pass` and never `fail`. That is the property the trust model asks for, and
here it holds by construction rather than by luck.

### Why `site.sharing_capability` is not cleared

Nothing reads it today, so nothing is wrong today. It sits in the evidence
envelope with the same shape as a measured fact, produced by the path whose
completeness is unproven, waiting for somebody to write a rule on it.

**Do not write that rule until the empirical test below has run.** The safe
value for the same question already exists at `sharing.capability`, from the
identity path, and `SPO-SHARE-001` uses it.

## What we do not know

Microsoft's warning is about `Get-SPOSite` **with `Limit` or `Filter`
supplied**. Our enumeration uses `Get-PnPTenantSite` with no identity, which is
a different cmdlet in a different module. No page we read states that it
inherits the limitation.

We do not know, and we are not assuming the equivalence in either direction.

### needs-tenant-validation

The question is empirical and cannot be settled from documentation:

```text
For a sample of the same sites, compare:
    Get-PnPTenantSite            (enumeration)  → StorageQuota, StorageUsageCurrent, SharingCapability
    Get-PnPTenantSite -Identity  (single site)  → the same three

Same values across several sites  → the risk is reduced, and this is recorded.
Any divergence                    → a collector defect is proven, and the
                                    enumeration path stops being evidence for
                                    those properties.
```

This is **not a blocker**. No live rule depends on the answer: the two sharing
rules use the identity path, and the storage rule is safe by design. It is
recorded here so that the next person to write a rule on an enumerated
property finds the question already asked.

## The open gap

`sharing.anonymous_link_expiry_days` is collected and cannot be interpreted.

Not because Microsoft failed to document the value, but because its meaning
depends on a companion property we do not collect. On `Set-SPOSite` the site
value is governed by `OverrideTenantAnonymousLinkExpirationPolicy`, a Boolean;
the tenant equivalent is `Set-SPOTenant -RequireAnonymousLinksExpireInDays`
([Set-SPOSite](https://learn.microsoft.com/powershell/module/microsoft.online.sharepoint.powershell/set-sposite?view=sharepoint-ps),
[Set-SPOTenant](https://learn.microsoft.com/powershell/module/microsoft.online.sharepoint.powershell/set-spotenant?view=sharepoint-ps),
checked on 8 August 2026).

Without the override flag, a site's expiry figure does not say whether it is in
force. Collecting the number without it is collecting a value with no meaning,
which is the reason no rule was written on it.

The type is `System.Int32`. **No page documents a meaning for `0`.** Whether it
means *never expires* or *not set* is not stated, and we do not say either.

---

## Re-evaluation after collecting the override

**2026-08-08, same day.** With `anonymous_link_expiry_override` now collected,
the candidate rule on anonymous link expiry was reconsidered. It is still
**deferred**, and the reason moved rather than disappeared.

What the override buys: a site with `override = true` is not following the
tenant policy, and that is a governance fact worth having. A site with
`override = false` is following it, and its own number is noise.

What is still missing, and it is two things:

1. **The tenant value is not collected.** "This site overrides the tenant" is
   only a finding when you can say what it overrode. More restrictive than the
   tenant and less restrictive than the tenant are opposite findings, and we
   cannot tell them apart. The tenant equivalent is
   `Set-SPOTenant -RequireAnonymousLinksExpireInDays`, and nothing in
   `Get-SpoEvidence.ps1` reads tenant-level settings at all.
2. **`0` is still undocumented.** With the override true and the days at zero,
   we cannot say whether the site has no expiry or has nothing set.

A rule written now would have to guess one of those two, and a rule that
guesses is worse than no rule: it produces a finding somebody acts on.

**Next step, when somebody takes it:** collect the tenant sharing settings as a
resource of their own. That is a new collection path rather than a new
property, and it unlocks more than this one rule, because every site-level
override becomes readable against what it overrode.
