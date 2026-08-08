# SharePoint agents and Copilot: the observable surface

**Enumerated 2026-08-08.** A discovery pass, not a plan. Nothing here is a rule,
and the last section says why that is the correct outcome rather than an
unfinished one.

Three sources, kept apart on purpose, because they carry different weight:

| Marked | Means |
|---|---|
| **documented** | Microsoft Learn says it, and the page is linked |
| **in the module** | read out of PnP.PowerShell 3.3.0's own types on this machine |
| **unproven** | neither, and therefore not usable for anything yet |

## What the domain actually is

Microsoft ships at least three distinct things under one word, and conflating
them would produce a rule that answers nobody's question:

1. **Agents in SharePoint** — end-user agents that answer questions about
   sites, pages and libraries. **Documented**: they are `.agent` files, they
   live in the site's *Site Assets* library, and the permissions on that file
   govern who can access or edit the agent.
2. **SharePoint Admin Agent** — an administrative governance experience over
   content sprawl, content lifecycle, oversharing and permissions.
   **Documented** prerequisites: SharePoint Advanced Management, plus the
   *SharePoint Advanced Management Administrator* role in Microsoft Entra ID.
3. **Copilot Chat agent controls** — tenant and AI administrators can block or
   unblock agents in the Microsoft 365 admin center. **Documented** limit:
   blocking currently affects availability in Copilot Chat only, and not
   OneDrive, SharePoint or Teams.

Only the first is a SharePoint object. The second is a licensed capability, and
the third is a control living somewhere else. **An engine that treated them as
one domain would be measuring three different things and reporting one number.**

## The permission fact, which is the important one

> **Documented.** "For users who access and use an agent in SharePoint, the
> agent's responses depend on each user's permissions to the agent's data
> sources. For instance, if a user has access to the agent but not to the site
> or document library it references, the agent's responses for this user don't
> include content from those restricted sources."

Two consequences, and they point in opposite directions:

- **Sharing an agent is not sharing its knowledge sources.** The `.agent`
  file's permissions decide who may use the agent; the user's own permissions
  decide what it can tell them.
- **An agent inherits the oversharing that already exists.** It grants no new
  access and it removes no existing exposure, so a site that was overshared
  before is overshared to a faster reader now.

This is the strongest content in the whole domain and it needs no new rule to
be worth writing about.

## What can be read, and with which tool

### With the module this collector already depends on

`Get-PnPCopilotAgent` exists in PnP.PowerShell 3.3.0. **In the module**, its own
synopsis: *"Returns the Microsoft Copilot Agents (\*.agent) in a site
collection."* One optional `-ServerRelativeUrl`, and it reads.

That matters more than it looks: **the agent inventory of a site is observable
without SharePoint Advanced Management**, through the ordinary file surface,
bounded by what the running identity may see.

`Get-PnPCopilotAdminLimitedMode` also exists and is **not** this domain: **in
the module**, its help names Copilot in Teams meetings and the Graph permission
`CopilotSettings-LimitedMode.Read`.

### Site properties, read from the module's own types

**In the module**, `Microsoft.Online.SharePoint.TenantAdministration.SiteProperties`:

```
RestrictContentOrgWideSearch                    Boolean
RestrictedContentDiscoveryforCopilotAndAgents   Boolean
RestrictedAccessControl                         Boolean
RestrictedAccessControlGroups                   Guid[]
```

**Documented** for the first only: `Get-SPOSite -Identity <url> | Select
RestrictContentOrgWideSearch` is how Microsoft says to read Restricted Content
Discovery for a site.

**The second is undocumented.** `RestrictedContentDiscoveryforCopilotAndAgents`
exists on the type, has a plausible name and a Boolean type, and no Learn page
describes it. **It is not evidence, and a rule on it would be a guess with good
grammar.** Whether it is the same flag under a newer name, a distinct one, or
vestigial, is unknown from here.

### Tenant properties, read from the module's own types

**In the module**, `Microsoft.Online.SharePoint.TenantAdministration.Tenant`:

```
RestrictExternalSharingForAgents                  Boolean
EnableAgentWorkerSharingDisclaimer                Boolean
DelegateRestrictedContentDiscoveryConfiguration   Boolean
KnowledgeAgentEnabled                             Boolean
KnowledgeAgentScopeMode                           KnowledgeAgentScopeMode
KnowledgeAgentSiteList                            IEnumerable
```

**A name divergence worth stopping on.** Learn documents the delegation switch
as `DelegateRestrictedContentDiscoverabilityManagement`; the installed module
carries `DelegateRestrictedContentDiscoveryConfiguration`. Same subject,
different identifier. **Whether they are one property, two, or one renamed, is
unknown**, and nothing may be built on either until a tenant says which name
answers. Assuming them equal is precisely the class of mistake this repository
just spent a cycle paying for.

### Only with SharePoint Advanced Management

**Documented**, in `Microsoft.Online.SharePoint.PowerShell` and not in PnP:

```
Start-SPOCopilotAgentInsightsReport      queues a report        WRITES
Get-SPOCopilotAgentInsightsReport        status, view, download reads
  -Content CopilotAgentsOnSites | TopSites | SiteDistribution
```

Two hard boundaries:

- **`Start-` creates tenant state.** It queues a job, it returns an Id and a
  status, and it is therefore outside what this collector may ever call.
  Reading a report somebody else generated is a read; generating one is not.
- **It is a different module.** Taking this on means a second PowerShell
  dependency and a licensing prerequisite, which is a product decision and not
  an implementation detail.

**Documented** without SAM: `Start-SPOAuditDataCollectionForActivityInsights`
enables the underlying collection. Also a write, and also out of scope.

## The trap this domain walks straight into

`RestrictContentOrgWideSearch` is a site property, and this repository has just
proven what filtered enumeration does to site properties: `Get-SPOSite`
documents twenty-two that it *"will not populate and may contain a default
value"*. That list does not name `RestrictContentOrgWideSearch` — **and the
absence of a name from a list is not a guarantee, particularly for a property
newer than the list.**

Its default is `False`, and `False` reads as *not restricted*. **A default that
means "unprotected" is the dangerous direction**, exactly as `Disabled` was.

> **Before any rule reads a site-level agent property, the enumeration path and
> the `-Identity` path are compared on a tenant, as `SharingCapability` was.**
> `needs-tenant-validation`, and not negotiable, because the failure would be
> silent and would read as safe.

## Where the normative question lands, and it lands badly

The rule contract requires a documented basis before a rule exists. Searching
this surface for one produces a clear and inconvenient answer.

**There is no documented requirement to enable Restricted Content Discovery.**
The opposite is closer to the text: Microsoft calls it *"designed as a
temporary governance control"* and cautions that *"excessive use can reduce the
amount of content available to organization-wide search and Microsoft 365
Copilot experiences, which can affect the completeness and relevance of search
results and AI-generated responses."*

So a rule saying *RCD should be on* would be an **opinion** wearing a
`documented-guidance` label, and a rule saying *RCD should be off* would be the
same mistake facing the other way.

**Documented and deprecated**: Restricted SharePoint Search is retiring, and
new enablement has been blocked since 31 July 2026. `Get-PnPTenantRestrictedSearchMode`
and `Get-PnPTenantRestrictedSearchAllowedList` are in the module and are a
dead end for new work. Recorded so nobody rediscovers them as an opportunity.

## What this cycle produces, and what it does not

**No rules.** Not one property here clears the contract: the observable ones
have no normative basis, and the one with a documented basis is not observable
without a second module and a licence.

**Knowledge is where the value is**, and it is unusually well supported. Three
articles are answerable today, entirely from documented text:

```
An agent can only know what its user can read
Why sharing an agent is not sharing its knowledge sources
How to inventory the agents on a SharePoint site
```

The third has a working collection path already: `Get-PnPCopilotAgent`, in the
module this product depends on, requiring nothing extra.

**Two facts owe a tenant run before anything is written as observed:**

1. Does `Get-PnPCopilotAgent` return anything on a site with an agent, and what
   shape does it return?
2. Do the enumeration and `-Identity` paths agree on
   `RestrictContentOrgWideSearch`?

**One question belongs to the owner, not the executor:** whether this product
takes a dependency on `Microsoft.Online.SharePoint.PowerShell` and a SharePoint
Advanced Management licence in order to reach the agent insights reports. That
is a second module, a second connection model and a licensing prerequisite for
the reader — a product decision with a cost, and the SAM-gated half of this
domain waits behind it.

## References

- [Manage access to agents in SharePoint](https://learn.microsoft.com/sharepoint/manage-access-agents-in-sharepoint)
- [Monitor agent usage in SharePoint](https://learn.microsoft.com/sharepoint/monitor-agent-usage)
- [Insights report on agents in SharePoint](https://learn.microsoft.com/sharepoint/insights-on-sharepoint-agents)
- [What is the SharePoint Admin Agent?](https://learn.microsoft.com/sharepoint/content-governance-agent)
- [Restrict discovery of SharePoint sites and content](https://learn.microsoft.com/sharepoint/restricted-content-discovery)
- [Prerequisites for SharePoint Advanced Management](https://learn.microsoft.com/sharepoint/sharepoint-advanced-management-prerequisites)
- [Agents admin guide for Microsoft 365](https://learn.microsoft.com/microsoft-365/copilot/agent-essentials/m365-agents-admin-guide)
- [Get-SPOCopilotAgentInsightsReport](https://learn.microsoft.com/powershell/module/microsoft.online.sharepoint.powershell/get-spocopilotagentinsightsreport)
- [Use PowerShell scripts for restricted SharePoint Search](https://learn.microsoft.com/sharepoint/restricted-sharepoint-search-admin-scripts) — the retirement notice
