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
| `site.sharing_capability` | enumeration | **documented not populated** | nothing, by construction | **not evidence**, see below |

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
Run it interactively. Never with a device code: a device-code session is not
the same consent or the same user context, and a validation that does not
reproduce the context validates nothing.

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

## The directory identity, which we said had no path

**Recorded 2026-08-16.** Every evidence document this engine writes carries
`tenant.id: null`, with the reason stated in `New-TenantIdentity`:

```powershell
# Null until a collection path for the directory identity is proven on
# a tenant. The host is an endpoint, and saying so is the point.
id = $null
```

**A path exists, and it is documented.** PnP.PowerShell ships `Get-PnPTenantId`,
and its own documentation states that the `-TenantUrl` form *does not require an
active connection to that tenant*:

```powershell
Get-PnPTenantId -TenantUrl <String> [-AzureEnvironment <AzureEnvironment>]
Get-PnPTenantId [-Connection <PnPConnection>]
```

Read from the project's documentation on GitHub rather than from memory, and
the parameter sets confirmed against the installed module.

**Why this matters more than one null field.** A tenant has one directory
identity and any number of addresses, and the engine says so in its own
contract. Today the host carries the identity as a compatibility measure, which
means a multi-geo satellite reads as a second tenant and two hosts of one
organisation cannot be folded together without inventing something. The id is
what settles it.

### needs-tenant-validation

Documentation proves the cmdlet exists and what it accepts. **Only a run proves
it returns a value**, which is the standing rule here and the reason this is
recorded rather than implemented into a rule:

```text
Run it interactively against a real tenant, and check:

    Get-PnPTenantId -TenantUrl https://<tenant>.sharepoint.com
    Get-PnPTenantId                     (with a connection open)

A GUID from both, equal        → the path is proven, and `tenant.id` can stop
                                 being null.
A value from one and not the
other                          → the form that works is the collection path,
                                 and the other is not.
Neither                        → the field stays null and this entry stays
                                 open, which is the honest outcome.
```

**Owner-only**, like every tenant validation here: it needs interactive access
this machine's executor does not have, and never a device code.

**What it unblocks.** Any consumer that authenticates has to be able to say
which organisation it is actually looking at, and it may not derive that from a
hostname somebody typed. Until this is proven, the honest answer after
authenticating is the host and `identity: not-established`, which is what
`connect` reports.

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

---

## Attempted, reverted, and the reason is the interesting part

**2026-08-08.** The next step above says to collect tenant sharing settings as
a resource of their own. It was implemented and then reverted the same hour,
because a test refused it for exactly the right reason.

The eleven tenant properties were validated on the cmdlet reference first, and
they exist: `SharingCapability`, `DefaultSharingLinkType`,
`DefaultLinkPermission`, `RequireAnonymousLinksExpireInDays`,
`ExternalUserExpirationRequired`, `ExternalUserExpireInDays`,
`SharingDomainRestrictionMode`, `PreventExternalUsersFromResharing`,
`ShowEveryoneClaim`, `FileAnonymousLinkType`, `FolderAnonymousLinkType`. The
rule schema takes `resource_type` as a free string, so no schema change was
needed for a level that had never existed here.

Then `test_each_slice_is_paired_with_a_profile_that_can_answer_it` failed:

> *slice tenant-sharing with profile sharing: no rule even applies to a
> tenant-sharing document*

That is the mirror of the rule at the top of this page. **Never build a rule on
a property until the collection path is proven to populate it** has a twin:
**never add a collection path that no rule can consume.** Evidence collected
for nobody is cost with no reader, and it ages without anyone noticing, because
nothing fails when it goes wrong.

### The dependency, stated plainly

```
tenant rule   needs   tenant evidence
tenant slice  needs   a tenant rule
```

It is not circular, and the way out is not to relax either side. A tenant rule
has to be justified before the collection exists, from documented guidance, and
that justification has not been done: nothing was read that says a tenant
*should* have `ShowEveryoneClaim` off, or that any of the eleven has a
recommended value. Asserting one would be `convention` dressed as
`documented-guidance`, which is the failure the basis field exists to prevent.

**The real next candidate is therefore smaller and comes first:** validate, on
Microsoft's documentation, whether any tenant-level sharing setting carries
published guidance. If one does, it justifies both the rule and the collection,
in that order. If none does, the tenant level is a `convention` decision with
product impact, and that belongs to the owner rather than to the executor.

---

## The normative question, answered

**2026-08-08.** The blocking question was whether Microsoft publishes guidance
for tenant-level sharing settings, or only describes them. It publishes
guidance, on a page that exists for that purpose:
[Best practices for sharing files and folders with unauthenticated users](https://learn.microsoft.com/Office365/Enterprise/best-practices-anonymous-sharing),
checked on 8 August 2026.

| Tenant setting | Guidance published | Verbatim | Basis it would carry |
|---|---|---|---|
| `RequireAnonymousLinksExpireInDays` | **yes** | *"files are often stored … for long periods … If such files are shared with unauthenticated people, this could lead to unexpected access and changes to files in the future. To mitigate this possibility, you can configure an expiration time for Anyone links."* | `documented-guidance` |
| `DefaultSharingLinkType` | **yes** | *"You can mitigate this risk by changing the default link setting to a link that only works for people inside your organization."* | `documented-guidance` |
| `FileAnonymousLinkType`, `FolderAnonymousLinkType` | **yes** | *"consider setting the file permissions to View and folder permissions to View or View and upload"* | `documented-guidance` |
| `SharingDomainRestrictionMode` | described, not recommended | the admin page explains what it does and when it is useful | `convention` if used |
| `ShowEveryoneClaim` | **no guidance found** | — | would be `convention` |
| `PreventExternalUsersFromResharing` | described only | *"By default, guests must have full control permission to share items externally."* | `convention` if used |

Three of the eleven carry published guidance with a stated rationale. That is
enough to justify a tenant rule and, with it, the collection it needs, built in
the same cycle. The other eight do not, and a rule on any of them would be a
`convention` with product impact, which is the owner's decision and not the
executor's.

**A second thing the same page settled.** It gives the exact command for the
site-level pairing:

```powershell
Set-SPOSite -Identity … -OverrideTenantAnonymousLinkExpirationPolicy $true -AnonymousLinkExpirationInDays 15
```

The override and the number are used together, by Microsoft, in their own
example. The property added to the collector earlier today is confirmed as the
right one, and the reading in the section above is confirmed as correct: the
days are meaningless without the flag.

**Still not settled:** what `0` means in either field. The admin interface
presents expiry as a checkbox plus a number, which suggests the number is only
read when the box is ticked, but no page states it and the suggestion is not a
source. A tenant rule should therefore be written on *whether expiry is
required at all*, not on the number, until that is proven.

---

## Closed: the tenant level exists, and it is two rules wide

**2026-08-08.** The second attempt shipped, and the difference from the first
is that the justification came first and the collection followed it.

| | First attempt | Second |
|---|---|---|
| Properties collected | 11 | **3** |
| Rules that read them | 0 | 2 |
| Profile | `sharing`, which selects site rules | **`tenant-sharing`**, its own |
| Outcome | reverted by a test | in the release contract |

What ships:

- `SPO-SHARE-003` — the organisation default sharing link should not be Anyone.
- `SPO-SHARE-004` — Anyone links should not be able to change what they open.
- Collector mode `TenantSharing`, reading `SharingCapability`,
  `DefaultSharingLinkType` and `FileAnonymousLinkType`. **Three, because three
  rules read three.** The other eight validated properties were not collected.
- Three fixtures: the permissive tenant, the mitigated tenant, and the tenant
  that forbids Anyone links entirely.

### Two things the build taught, which are not in the rules

**A new level needs a new profile, not a bigger old one.** Registering the
slice against `sharing` failed the pairing test a second time, and correctly:
that profile selects site rules, and a tenant document has no site in it. The
symptom was identical to the first failure and the cause was not, which is the
argument for keeping the test's message about *documents* rather than *rules*.

**Applicability has to be decided before evidence is required.** The
internal-only fixture carries `file_anonymous_link_type` as `missing`, which is
honest — the property has nothing to describe where the capability is
`Disabled`. If evidence requirements were checked first, every organisation
that forbids Anyone links would report `unknown` on a question that does not
apply to it. The engine already does this; there is now a test that says so, so
that a future change to the ordering fails here rather than in a customer's
report.

### Still open, unchanged by this cycle

`0` in either expiry field, and the tenant expiry value itself. Collecting
`RequireAnonymousLinksExpireInDays` is now cheaper than it was — the mode
exists — and it is still not collected, because the rule that would read it
cannot be written while `0` is undefined. **The cost of the collection was
never the reason to wait.**

---

## Deferred, durably: anonymous link expiry

**2026-08-08.** Scored and refused rather than left as an open intention. The
record is here because this is where the collection path lives; the queue entry
is in [NEXT-SLICE.md](NEXT-SLICE.md).

```
candidate   a tenant rule on whether Anyone links are required to expire
gate        evidence integrity
gap         0 semantics not documented
score       0  (readiness 0 eliminates it; the product of five factors)
status      deferred
```

Microsoft recommends configuring an expiration time for Anyone links, and the
only collectable value is an `Int32` whose `0` carries no documented meaning.
**Nothing available distinguishes "expiry is not required" from any other
special reading of zero**, so a rule would have to guess, and a rule that
guesses produces a finding somebody acts on.

**The collection path is not the obstacle.** The `TenantSharing` mode already
exists, so `RequireAnonymousLinksExpireInDays` would be one more property. It
stays uncollected because the rule that would read it cannot be written, and
evidence collected for nobody is cost with no reader.

**What would unblock it:** Microsoft documenting the value, or a tenant
observation that settles it empirically. The admin interface presenting expiry
as a checkbox plus a number suggests the number is read only when the box is
ticked, and a suggestion is not a source.

**Sharing stays closed.** A closed domain may contain deferred candidates:
deferred means today's evidence cannot support implementation, not that the
domain is unfinished. It reopens when one of the two unblocking facts appears.

---

## Closed: the enumeration path is documented not to populate this

**2026-08-08, against a sandbox tenant, interactive.** The question this audit
opened is closed. The behaviour was reproduced, and then the cause was found in
Microsoft's own documentation rather than inferred from the symptom.

### What was observed

Five sites, read both ways:

| Site | `SharingCapability` enumerated | by `-Identity` |
|---|---|---|
| root | **`Disabled`** | **`ExternalUserAndGuestSharing`** |
| root (second) | `ExternalUserAndGuestSharing` | same |
| `/search` | `Disabled` | same |
| `/sites/allcompany` | `ExternalUserSharingOnly` | same |
| `/sites/DigitalInitiative…` | `ExternalUserSharingOnly` | same |

One in five disagreed, and in the dangerous direction: a site that permits
external sharing with guests reported as sharing disabled.

### What should have been observed

The site's effective `SharingCapability` — the same value the per-site
retrieval returns, since both name one property of one site.

### Why they differ, and it is documented

`Get-SPOSite` states the limitation on its own reference page:

> If the Limit or Filter parameters are provided then the following site
> collection properties will not be populated and may contain a default value:
> […] **SharingCapability**, SharingDomainRestrictionMode.

Twenty-two properties are named. `SharingCapability` is one of them.

The bridge from that page to this collector is the API each path calls.
`Get-PnPTenantSite` without `-Identity` calls
`Tenant.GetSitePropertiesFromSharePointByFilters`, the filter-based enumeration
the documented limitation describes. With `-Identity` it calls
`Tenant.GetSitePropertiesByUrl` or `GetSitePropertiesById`, which the limitation
does not cover.

`Disabled` is the zero member of the enum: exactly the "default value" the
documentation names.

**Cause status: documented and reproduced.** Not inferred, and not a guess about
an undocumented internal.

### The part the documentation explains and the reassuring reading does not

Four sites of five agreed. That looks like a rare fault; the documentation says
otherwise. The wording is *may contain a default value* — population is not
guaranteed, rather than uniformly absent. **Agreement on four sites is the lack
of a symptom, not the presence of correctness**, and nothing in the API contract
says which site gets a populated value on which call.

That is why the decision is not "retry", and not "compare and keep the more
permissive value".

### The decision that follows

**The enumeration path is not accepted as evidence for any property on the
documented list.** Only the per-site retrieval is authoritative for them.

- `site.sharing_capability` is **no longer collected as a fact**. The collector
  writes `not-supported` with the reason and a pointer to the identity path.
  Recorded rather than deleted: a future reader deserves to find out why it is
  absent instead of wondering whether anybody thought about it.
- **No live rule was affected**, which the audit predicted and this confirms
  rather than assumes: `SPO-SHARE-001` reads `sharing.capability` from the
  identity path.
- The rest of the enumerated map — `Template`, `LockState`,
  `StorageUsageCurrent`, `StorageQuota`, `LastContentModifiedDate`, `HubSiteId`
  and `GroupId` — appears nowhere on the documented list, which is why storage
  agreed on all five sites. That is now a checked fact rather than an
  observation: a test fails if any of the twenty-two ever enters that map, and a
  second test keeps the list printed below in step with the list the guard
  holds.
- The five properties `Sharing.psm1` reads that **are** on the list —
  `SharingCapability`, `DefaultSharingLinkType`, `DefaultLinkPermission`,
  `AnonymousLinkExpirationInDays` and
  `OverrideTenantAnonymousLinkExpirationPolicy` — reach it from
  `Get-PnPTenantSite -Identity`. `SensitivityLabelInfo` comes from
  `Get-PnPSite`, a different API that the limitation does not describe.

### The twenty-two, as documented

```
AllowDownloadingNonWebViewableFiles
AllowEditing
AllowSelfServiceUpgrade
AnonymousLinkExpirationInDays
ConditionalAccessPolicy
DefaultLinkPermission
DefaultLinkToExistingAccess
DefaultSharingLinkType
DenyAddAndCustomizePages
DisableCompanyWideSharingLinks
ExternalUserExpirationInDays
InformationSegment
LimitedAccessFileType
OverrideTenantAnonymousLinkExpirationPolicy
OverrideTenantExternalUserExpirationPolicy
PWAEnabled
SandboxedCodeActivationCapability
SensitivityLabel
SharingAllowedDomainList
SharingBlockedDomainList
SharingCapability
SharingDomainRestrictionMode
```

### The lesson, and it is bigger than this property

> **A property with the correct type and a plausible value is not evidence
> until its collection path is documented or proven to populate it. A path that
> returns a default value on failure produces a wrong answer with no marker on
> it.**

`Disabled` is a real member of the enum. It has the right type, a sensible
meaning and nothing to distinguish it from a reading. **A null announces itself;
this does not.** Every defence this engine has — required evidence,
applicability gates, the five states — is built to catch an absence, and none of
them catches a confident wrong answer.

The working rule for the next collector: **before mapping a property out of a
bulk or filtered call, read what the cmdlet reference page says that call
populates.** Here the page named the property outright, and the whole defect was
one paragraph away from never existing.

### References

- [Get-SPOSite](https://learn.microsoft.com/powershell/module/microsoft.online.sharepoint.powershell/get-sposite) — the documented limitation and the list of twenty-two
- [Get-PnPTenantSite](https://pnp.github.io/powershell/cmdlets/Get-PnPTenantSite.html) — the cmdlet this collector calls
- `pnp/powershell`, `src/Commands/Admin/GetTenantSite.cs` — which Tenant API each parameter set calls

### Still open

`Get-PnPEntraIDAppPermission` was refused: *Forbidden (403), insufficient
privileges*. That is the Graph, not SharePoint, and reading application
permissions needs `Application.Read.All` across the whole directory. **Recorded
as coverage, not as a hole to force**: whether that scope is worth granting is
the owner's decision, and the SPFx candidate waits behind it.
