# Milestone A: SharePoint Online, end to end

**Closed at `1.0.0-beta.1`, 2026-08-06.**

Epic A was a single claim: that this model can carry a service from a
PowerShell call to a sentence a person can act on, without guessing anywhere
along the way. Eight vertical slices, each one closed only when the collector
observed the fact, the schema accepted it, a fixture existed, a rule with a
declared `basis` read it, every outcome was reachable, the report explained
it, and the collector was still provably read-only.

Sixteen rules, ten collector modes, seven profiles, ten commands, 350 tests at
91 per cent coverage. Beta because the model has stopped moving, not because
the rule set is finished.

---

## The eight slices

| Slice | Collector mode | Rules | What the tenant changed |
|---|---|---|---|
| **Sites** | `TenantSites` | SPO-SITE-002 | 53 sites enumerable by a delegated identity, and the number is a lower bound rather than a total |
| **Sharing** | `SiteSharing` | SPO-SHARE-001, 002 | `SharingCapability` is a tenant property about a site, not a site property. `DefaultSharingLinkType: None` means "inherits the tenant", so the first version of SPO-SHARE-002 would have passed 53 sites knowing nothing |
| **Permissions** | `UniquePermissions` | SPO-LIST-001, 002, 003 | `is_application` outranks `is_system`: Site Pages and Site Assets carry both flags, and reading system first filed a site's own pages under plumbing |
| **Capacity** | `TenantSites` | SPO-SITE-001, 003 | A site with no quota is not a site with room |
| **Modernity** | `Modernity` | SPO-MODERN-001, 003, 004 | `CustomMasterUrl` is set on every site to the product default, and the path carries the site, so comparing paths reported every non-root site |
| **SPFx** | `SpfxCatalog`, `SpfxPages` | SPO-SPFX-001 | A page count that did not reconcile: 9 pages, 8 inspected, 7 unreadable. The collector now marks the affected facts `invalid` rather than publishing arithmetic that cannot be true |
| **Activity** | `Activity` | SPO-ACTIVITY-001 | Every site had been touched on the day of collection by a system process. Two of three had gone over a year without a person. The rule reads `LastItemUserModifiedDate`, and that difference is the whole rule |
| **Classification** | `Classification` | SPO-CLASS-001, 002, 003 | An empty `SensitivityLabelId` is an observation, not a gap. Reporting it as `missing` made `classified: false` an answer derived from an admission of ignorance |

---

## What the validating tenant actually said

One tenant, `joaolivio.sharepoint.com`, 53 sites, delegated identity. It is
small and it is one, and every number below is a fact about it rather than
about Microsoft 365.

- **47 of 53 sites** returned classification evidence. Six refused outright:
  *Attempted to perform an unauthorized operation*. A delegated identity is
  not a tenant view, and this is what that costs.
- **0 of 47** carried a sensitivity label. **0 of 47** carried a
  classification string. The tenant has not adopted container labels, so
  SPO-CLASS-001 fails on every site — a true answer to the question asked and
  a misleading one to the question a reader will have in mind. That is written
  into the rule's own limitations rather than left for somebody to discover.
- **22 of 47** are connected to a Microsoft 365 group. SPO-CLASS-003 has 22
  real failures and SPO-CLASS-002 has none: no site carries a label, so the
  rule about labels that cannot be named has never fired outside a fixture.

---

## What was deliberately not built

Each of these was reachable and was left out, because the rule that would have
covered it could not have been written honestly.

- **A fourth classification rule.** The specification allowed one of type
  `opinion`, on condition that a real case existed. The tenant is uniform: no
  labels, no classification strings, nothing to have an opinion about. Writing
  it would have meant inventing the case it was meant to describe.
- **`IsTeamsConnected`.** It lives on the tenant record, and PnP refuses to
  switch to the administration context after a device login. `GroupId` answers
  the weaker question with no administrative right at all, and a
  Teams-connected site is group-connected, so nothing escapes the rules. The
  report simply cannot say which of the two it is looking at.
- **Site privacy.** `PrivacySetting` is not a property of `SPOSite`. It was in
  the specification and it is not in the product, so it is not in the
  evidence.
- **A rule about unused SPFx solutions.** `web_part_id` is not a package id.
  The words "unused", "orphaned" and "not in use" appear nowhere in this
  repository for that reason.
- **A rule about anonymous-link expiry.** `0` is ambiguous between "no expiry"
  and "not set", and the product does not distinguish them.
- **A classification profile.** A profile selects rules, and the three
  classification rules are the only ones reading that evidence. A profile
  naming them would repeat what the evidence already says.

---

## The architecture, frozen

Nothing in this list changes without evidence that motivates it, per
[CHANGE-POLICY.md](CHANGE-POLICY.md).

1. **Six outcomes.** `pass`, `fail`, `unknown`, `not-applicable`,
   `invalid-evidence`, `error`. `unknown` is never a pass. `error` is not
   authorable by a rule.
2. **Resolution order.** `invalid-evidence` → `not-applicable` → `unknown` →
   `pass`/`fail`.
3. **A true condition means `fail`.** Every rule states the case being
   reported.
4. **Five basis types**, authored and never inferred: `requirement`,
   `documented-limit`, `documented-guidance`, `convention`, `opinion`. A
   source never decides the type.
5. **Bounded evaluation.** Evidence is monotonic: a partial count is a lower
   bound, and each operator has a side on which a partial answer is already
   final.
6. **Six validation layers**, ordered by scope, each with exactly one owner.
7. **The collector observes and never judges.** No `is_compliant`, no score,
   no recommended action, and no write path — proven by parsing the file in
   CI.
8. **Classification labels, never filters.** A class moves a resource down a
   report and never out of one.

---

## What Milestone B would have to answer

Not commitments. The questions this milestone leaves open, in the order they
would matter to somebody using the tool.

- **Application identity.** Every number here carries "as far as this
  identity could see". An app registration with `Sites.Read.All` would remove
  that clause, and the `identity_kind` field already exists to record which
  one produced a document.
- **Coverage across a run of many sites.** Six sites produced no evidence at
  all, and a report over the other 47 says 47 without saying "of 53". The
  envelope records coverage per document; nothing records it per run.
- **A second service.** The evidence schema is service-agnostic and has never
  been asked to prove it. Exchange or Entra would be the test.
- **A second tenant.** Nine defects in this milestone were found by running
  against a real tenant and none by reading. One tenant found nine. It is not
  a reason to believe there are no more.
