# PnP as a discovery surface

**Inventoried 2026-08-08.** The second instance of the pipeline that
`OBSERVABLE-SURFACE.md` was the first of. Not a generalised discovery engine:
generalising the shape of a second thing from the first one is inventing it.

> **PnP is a discovery surface and an implementation ecosystem, not a normative
> authority.** Microsoft Learn remains the source for documented requirements,
> limits and guidance. PnP reveals observable properties, supported mechanisms,
> implementation patterns and contribution opportunities. **A sample proves
> something can be read; it never proves it should be a certain value.**

That distinction is not pedantry. A rule whose `basis` says
`documented-guidance` must cite a page that gives guidance, and a community
script is not one, however good it is.

## What was counted

`pnp/script-samples`, **394 samples**, classified by governance area against
what this engine already covers.

| Area | PnP samples | Rules here | |
|---|---|---|---|
| Sites and inventory | 74 | 3 | |
| Lists and content | 64 | 3 | |
| Modernity and classic | 38 | 3 | |
| Sharing and external | 36 | 4 | |
| Permissions | 31 | 3 | |
| **SPFx and apps** | **25** | **1** | **widest gap** |
| Teams and groups | 17 | 0 | no service yet |
| Activity and lifecycle | 14 | 1 | |
| Classification | 9 | 3 | |
| Flows and automation | 4 | 0 | no service yet |

Sample count is **attention, not importance**: it says where a community with
real tenants spends its time, which is a signal about what people actually have
to do and not about what matters most.

## The first domain, and why

**SPFx and apps.** One rule against twenty-five samples is the widest ratio in
a service this engine already covers, and three samples name a fact that is
observable and entirely uncollected:

```
spo-get-spfx-apipermissions
spo-delete-unused-spfx-apipermissions
spo-find-spfx-packages-installed-tenant-sitecollection-appcatalog
```

**API permissions granted to SPFx solutions.** Confirmed observable in the
installed module rather than assumed:

```
Get-PnPEntraIDAppPermission
Get-PnPEntraIDServicePrincipalAssignedAppRole
Get-PnPEntraIDServicePrincipalAvailableAppRole
```

A tenant grants Graph scopes to the SPFx service principal, every solution
shares them, and nobody reviews them after the deployment that asked for them.
That is a governance question with a shape this engine already knows how to
answer.

It also produces work on all three products in one pass, which is what makes a
domain worth opening rather than a rule worth writing:

```
engine     a collector mode and a rule, if Microsoft documents guidance
content    how the permission is read, and what an over-granted scope costs
           at migration
upstream   the samples delete unused permissions; nothing inventories them
           against what solutions actually use
```

## What has to happen before any of it

**Nothing is collected yet, and nothing should be.** The rule contract's order
holds:

```
1  enumerate the observable surface of SPFx API permissions
2  find whether Microsoft documents guidance on reviewing them
3  only then decide between a rule, a Knowledge article, or neither
```

Step 2 is the one that decides. If Microsoft describes the mechanism and
recommends nothing, this is a `convention` with product impact, and that is the
owner's decision rather than the executor's — exactly where the tenant sharing
settings landed, and eight of eleven were refused there.

## The other end of the pipeline

**A contribution is owed when one is found, and not before.** Reading a source
well enough to build on it is reading it well enough to find what is wrong with
it, but manufacturing a pull request to have contributed is the same failure as
manufacturing an article to fill a cell in a coverage matrix.

Nothing has been found yet. The inventory above is a map, not a debt.
