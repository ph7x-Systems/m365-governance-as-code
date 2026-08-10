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

## The next slice, and the cmdlet everybody assumes answers it

**`Get-SPOM365AgentAccessInsightsReport` does not say who may use an agent.**
The page it belongs to is *Monitor agent access to SharePoint and OneDrive*,
and the direction is the opposite one: which agents reached which sites,
derived from unified audit data. That is history, not permission.

The distinction matters enough to write down before anybody builds on it:

```
who may USE the agent      the .agent file's permissions. An ordinary file
                           read, no report and no extra licence, and this
                           engine already reads unique permissions on list
                           items for the LIST domain.

what the agent REACHED     the access insights report. SAM or Copilot
                           licence, audit-derived, and a different question
                           with a different answer.

what the agent may reach   the sources in its own definition, which the
                           inventory already collects.
```

**Three questions, and only the first is "who can use this agent".** Reading
the report as an answer to it would have produced a slice that needs a licence
to answer something the file already carries.

**Documented limits on the report, for whenever that third slice opens:**

```
one report per range (1, 7, 14, 28 days), so four at most
a new report for a range REPLACES the old one
24 hours between generations, up to 48 for a large tenant to have data
"might not include every audit event"
Start- queues a job, so it writes and stays outside the collector
data collection itself needs Start-SPOAuditDataCollectionForActivityInsights
```

The last line is the one that decides scope: the report is not a read of
current state, it is a read of a job somebody had to start.

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

## Deferred, and what it takes to resume

**Updated 2026-08-10.** A tenant run reached a site, enumerated agents and
returned zero. The call works. The agent object was never exercised, so
everything the model says about an agent's shape is still unproven, and the
`New` > `Agent` surface was not offered on the site that was read. Why it was
not offered is not established.

So `SPO-AGENT-001` is a **candidate, not a rule**. There is no YAML, no profile,
no fixture and no generated model for it, and that is deliberate: a rule with a
fixture somebody invented is a rule that passes its own tests and nothing else.

The slice resumes when all five of these are true. Not four.

| | |
|---|---|
| 1 | a **non-production** tenant that can create agents in SharePoint |
| 2 | edit permission on the validation site, held by the running identity |
| 3 | **Agent A** saved with explicit sources — one folder, one file, instructions present |
| 4 | **Agent B** attempted with no source at all, and the result recorded either way: saved, refused with the exact visible message, or the last source impossible to remove |
| 5 | `tools/validate-agents.ps1` rerun against that site, and its output committed |

The fourth is the one the rule turns on. If the interface refuses to save an
agent with no source, that refusal is worth more than any fixture: it would mean
the documented state — both source properties omitted — cannot be reached
through the SharePoint experience at all, and a rule that fails agents for
reaching it would be failing them for something they cannot do.

Production is not an acceptable substitute for condition 1. Creating validation
agents in a tenant that holds customer data to prove a governance rule would be
the exact behaviour this product exists to argue against.

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
