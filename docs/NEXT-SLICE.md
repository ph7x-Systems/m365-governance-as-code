# Continuous execution queue — Microsoft 365 governance surfaces

**Programme state:** `ACCEPTED_FOR_CONTINUOUS_EXECUTION`

**Owner decision:** 2026-08-17

**Execution base:** `readme-install-platforms@35e72dc` (PR #24, `QA_READY`)

**Integration rule:** execute without waiting for #24 to merge; after an authorised
merge, rebase and prove the isolated delta. The Executor never merges.

This file is the canonical Engine queue. Every numbered slice in this file is already
accepted for execution. The Executor starts at the first slice that is not `QA_READY`
and continues in order without conversation, scratchpads, roadmap ratification or a
new owner approval. Completed work is removed from the active queue rather than kept
as queue history; its PR, commits and release evidence remain the historical record.

The first active slice is `IDENTITY-CA-001`. Its full contract follows. The remaining
cards are executable contracts combined with the common contract below; they are not
ideas, options or a backlog requiring refinement by the Executor.

## A capability is not shipped until it is installable

> **Merging a collector is not shipping it.** A capability slice reaches
> `SHIPPED` when the release that carries it is published to the public index and
> proven installable from there by `tools/post-release-check.sh` — not when the
> branch is green, and not when a local wheel works.

The trigger is a public capability: a contract, a rule, a collector or a CLI
surface that somebody outside this repository consumes. An internal fix is not one.

Until the current slice is `SHIPPED`, no new collector starts here. An engine that
keeps adding surfaces ahead of its own published releases accumulates capability
nobody can install, and the gap is invisible from inside the branch that created it.

```text
IDENTITY-CA-001

Engine      IN PROGRESS

Slice       OPEN
```

`IN PROGRESS` becomes `SHIPPED` when the release is on the public index and the
post-release gate has proven it from there. Only then does `IDENTITY-APPS-001`
start.

## PUBLIC-MANIFEST-001 — one published description of what this engine can do

**Accepted 2026-08-17, and it runs before the Identity surface expands further.**

### Question

> What does this engine collect, decide and promise, in one document a consumer
> can read without cloning the repository?

### Why

The facts exist and are scattered across the places that produce them: the
slice registry knows the collectors, the rule files know the rules and their
basis, the schemas know the contracts, `docs/COLLECTOR-LIVE-MATRIX.md` knows
what has been proven against a tenant, and the source audits know the
permissions and limitations. Nothing joins them, so every consumer that wants
the whole picture rebuilds it by hand — and a hand-built copy of a fact this
repository owns is a second authority that goes stale silently.

### Scope

Publish a versioned contract carrying, for each capability: its collectors, the
Microsoft API each reads, the permissions each requires, the evidence contracts
it produces, the rules that consume it with their basis and limitations, the
relationships between them, and what live validation has established. Generated
from the registry, the rules, the schemas and the matrix — never hand-written,
and refused by the gate if it drifts from what it describes.

`registry.contract(name)` and the existing schema bundle are the pattern; the
manifest is one more contract published the same way, not a new mechanism.

### What it is not

Not state, not a queue, not a roadmap. A capability appears in it when it is
implemented and shipped, and never because it is planned.

## Why this slice

The next service is Microsoft Entra ID, starting with the access-policy surface that
can support several governance conclusions. This is one vertical capability, not a
set of unrelated collectors.

SharePoint tenant sharing, site sharing, site inventory and site classification
already exist. They are regression surfaces, not work to rebuild. Microsoft Secure
Score is a Microsoft projection and never replaces Engine evidence or rules.

## Question

> What access-policy configuration did this identity observe for the tenant, what
> could it not read, and which defensible conclusions can the Engine draw from the
> current Microsoft contract?

Read the specification before implementation. If a field cannot support a conclusion,
collect it only when the report is an explicit consumer and says exactly what was
observed. Never invent a threshold or interpret an absent value from its shape.

## Official surface to inspect

Checked on 2026-08-17; re-open the live pages before coding:

| Surface | Read operation | Least application/delegated permission documented |
|---|---|---|
| Conditional Access policies | `GET /v1.0/identity/conditionalAccess/policies` | `Policy.Read.All` |
| Named locations | `GET /v1.0/identity/conditionalAccess/namedLocations` | `Policy.Read.All` |
| Security Defaults | `GET /v1.0/policies/identitySecurityDefaultsEnforcementPolicy` | `Policy.Read.All` |

Authentication-strength details used by a policy are embedded in
`grantControls.authenticationStrength`; they are not a fourth collection endpoint.
Preserve the embedded identifier, policy type, satisfied requirements and allowed
combinations returned by the policy. Do not add a separate authentication-strength
request unless a later accepted slice establishes a distinct consumer and re-audits
its current contract.

`Policy.Read.All` is the documented least delegated and application permission for
all three operations above, with no higher-privileged alternative documented. A
delegated identity also needs one of the directory roles accepted by the current
operation documentation, such as Global Reader, Security Reader or Conditional
Access Administrator. Permission without an accepted directory role is denial, not
an empty tenant. The Graph host is configuration because the four supported national
clouds use different endpoints.

Primary references:

- <https://learn.microsoft.com/graph/api/conditionalaccessroot-list-policies?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/conditionalaccessroot-list-namedlocations?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/identitysecuritydefaultsenforcementpolicy-get?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/resources/policyroot?view=graph-rest-1.0>

`docs/EXTERNAL-SOURCES.json` already permits factual discovery and short attributed
reference to Microsoft Learn. Copy no Microsoft prose or sample code.

## Scope

### A. Source and collection-path audit

Before production code, record in the durable slice evidence:

1. exact v1.0 endpoints and response resource types;
2. least privilege separately for delegated and application identity;
3. supported national clouds and licensing prerequisites;
4. pagination and consistency behaviour;
5. throttling (`429`/`Retry-After`), transient failure and retry limits;
6. `401`, `403`, absent resource, empty collection and unsupported-property meaning;
7. evolvable enums and `unknownFutureValue` handling;
8. fields omitted unless explicitly selected or returned only with extra permission;
9. which rule basis is requirement, documented guidance, documented limit or convention;
10. every referenced identifier that the slice can and cannot resolve.

The source audit is the first internal step, not a communication checkpoint or a
stopping point. If it changes the question, correct the durable contract and continue
directly into implementation. Do not send an interim report or wait for acknowledgement.
Escalate only a material product decision that the sources and existing architecture
cannot settle.

The initial audit left four live questions for tenant validation: actual licensing,
pagination observed in this tenant, effective throttling limits and whether different
accepted delegated roles return different fields. They do not block the provider,
fixtures, contracts, rules, tests or subsequent queue items. Record only what the live
run establishes; do not promote an observation into Microsoft-wide semantics.

### B. Graph read-only acquisition

Add the smallest provider boundary that can read Microsoft Graph without coupling the
Engine model to terminal text or to the existing PnP collector. Preserve the current
SharePoint path unchanged.

The provider must:

- permit only `GET` for this slice and reject mutation structurally;
- accept externally supplied authentication; never create consent, credentials,
  applications, secrets or certificates;
- record source API, identity kind and granted scopes/app roles without secret values;
- derive `observed_tenant_id` only from the authenticated session/token claim;
- keep public `resolved_tenant_id` distinct from observed session identity;
- follow pagination and bounded `Retry-After` behaviour;
- return structured unavailable/partial results rather than parsing terminal prose;
- preserve requested/completed/unavailable coverage in the collection manifest;
- never translate permission denial, unsupported surface or licence absence into an
  empty compliant tenant.

### C. Product capability

Expose one CLI slice named `conditional-access` that collects, in the same run:

1. Conditional Access policies;
2. named locations referenced by those policies;
3. Security Defaults state when the official read path and permission are proven;
4. authentication-strength details embedded in each policy response.

Unresolved users, groups, roles, applications or locations remain stable native IDs
with explicit resolution state. This slice does not silently add directory-wide
inventory to make a label look friendly.

The output must be consumable by:

- JSON/Markdown/HTML report as an access-policy inventory;
- Assessment and RunSet;
- comparison/diff across two assessments;
- governance rules whose Microsoft basis survives the audit.

An inventory item may ship without a rule only when the report consumer is named and
the documentation explains why Microsoft provides no normative conclusion. No rule
is created merely because a field exists.

### D. Evidence and tests

Use only synthetic public fixtures. Cover at least:

- enabled, disabled and report-only policies;
- include/exclude targets and an unresolved target;
- IP and country named locations without real IPs or names;
- built-in and custom authentication strength references when supported;
- Security Defaults enabled, disabled and unavailable when supported;
- empty tenant distinguished from permission denied;
- delegated `Policy.Read.All` without an accepted directory role distinguished from
  an empty tenant;
- pagination;
- `429` with `Retry-After` and bounded exhaustion;
- `401`, `403`, malformed response and partial second page;
- an unknown future enum preserved without becoming pass;
- two tenants proving no cross-tenant combination;
- structural proof that no mutating HTTP method is reachable;
- collection manifest, Assessment, report and diff;
- clean installed-wheel execution outside the checkout.

Tests assert outcomes and provenance, not mocks alone. A negative test must show that
removing pagination, tenant isolation, permission-denied handling or the read-only
guard makes the contract fail.

## Authorised live observation

The owner authorised read-only tests against:

- `https://y75hx-admin.sharepoint.com/`
- `https://y75hx.sharepoint.com/`

The two addresses were already observed resolving publicly to the same directory.
Do not publish the directory ID or any live tenant value.

Use existing authentication only, in this precedence:

1. `ENTRAID_APP_ID`;
2. `ENTRAID_CLIENT_ID`;
3. `AZURE_CLIENT_ID`;
4. existing managed PnP configuration.

Never print the selected value. Never create missing configuration. The current
SharePoint regression uses the established interactive flow without `--device-login`.

For Graph, inspect existing consent only after the provider exists:

- consent sufficient: collect read-only and record a sanitised result;
- missing `Policy.Read.All`: record `BLOCKED_OWNER_POLICY_READ_ALL` for live
  observation only, then finish code, fixtures, contracts, rules, reports and PR;
- no authentication configuration: record `BLOCKED_OWNER_AUTH_CONFIG` for live
  observation only and continue the same way.

No live hostname, tenant ID, user, group, application ID, policy name, named-location
name, IP range or other identifier enters the public repository. Validate live output
in an ephemeral directory, retain only non-identifying states/counts and destroy it.

## Explicit exclusions

Do not include in this slice:

- app registrations, enterprise applications, service-principal inventory;
- OAuth grants or app-role assignments;
- per-user authentication methods or MFA registration reports;
- PIM, privileged-role assignments, administrative units or break-glass discovery;
- cross-tenant access or external identities;
- risky users, risky sign-ins or sign-in logs;
- remediation, consent, policy simulation or any write operation;
- Exchange, Teams, Intune, Defender, Purview, Power Platform or Copilot expansion.

Configuration, access control and telemetry remain separate evidence dimensions.

## Definition of Done

`IDENTITY-CA-001` closes only when all applicable items hold:

- [ ] official audit above is recorded with review date and precise permissions;
- [ ] Graph provider is read-only by construction and independently tested;
- [ ] `conditional-access` is reachable from the installed CLI;
- [ ] provenance and coverage distinguish observed, partial, denied and unsupported;
- [ ] policies and dependencies are lossless, tenant-scoped and diffable;
- [ ] every rule has collectable evidence and an attributed Microsoft basis;
- [ ] inventory without a rule has an explicit report consumer and limitation;
- [ ] Assessment, JSON, Markdown, HTML and comparison consume the new resources;
- [ ] synthetic fixtures contain no tenant-derived identifiers or copied values;
- [ ] focused tests, full Engine release contract and clean-clone/wheel checks pass;
- [ ] authorised live observation passes or carries one exact owner-only blocker;
- [ ] README/reference/CLI help and `docs/EXTERNAL-SOURCES.json` are current;
- [ ] branch, SHA, checks, evidence and next action are recorded in the PR;
- [ ] PR is mergeable, clean and has no unresolved review; the Executor does not merge.

## Continuous execution constitution

### Selection and continuation

1. The first queue item without durable `QA_READY` evidence is the current slice.
2. Complete it vertically, push its branch, open or update its PR, follow CI and
   resolve review findings.
3. A pending PR, CI run, review or authorised merge is not idle time and does not
   block the next slice. Branch the next slice from the last proved head and declare
   the dependency in its PR. After an upstream merge, rebase and prove the isolated
   delta.
4. Keep at most one implementation slice active and one completed slice awaiting
   integration. Waiting for external state does not require a conversation: monitor
   it while continuing the current eligible work in the foreground.
5. Never merge, deploy, publish, create consent, change tenant state or manufacture
   credentials. Those actions remain outside execution authority.
6. Do not stop after an inventory endpoint, collector or test. Continue until the
   capability is reachable through the installed product and every named consumer.
7. Do not ask the owner which accepted slice comes next. This file answers that
   question. Ask the Auditor only when a contradiction changes product meaning or no
   safe, documented path remains after the blocker rules below.
8. Internal items, phases, source audits and checkpoints never produce a hand-off or
   pause. Continue within the same turn and working sequence until the whole slice is
   `QA_READY` or an exact blocker exhausts every unaffected action. Progress messages
   are permitted only when execution continues; they never request acknowledgement.

### Common vertical contract for every slice

Every queue card inherits this sequence and is incomplete if any applicable step is
missing:

1. Re-open the current official Microsoft operation and resource documentation before
   implementing each surface; search results, error messages, remembered behaviour and
   documentation for another tool are not authority.
   Record review date, API version, availability, national-cloud support, licence,
   least delegated and application permissions, pagination, throttling, absence,
   partial-response and evolvable-enum semantics. Do not code from memory.
2. Record which source answers which question. Microsoft Learn owns Microsoft API
   operations, permissions, national clouds, resource semantics, limits and guidance.
   A third-party tool is governed by its own documentation at the pinned version.
   Runtime observation proves only what that run returned.
3. Inspect existing repository contracts and reuse the owning provider, resource,
   provenance, manifest, Assessment, RunSet, rule, report and comparison patterns.
   Extend existing SharePoint collectors; never duplicate them.
4. Add the smallest read-only acquisition boundary. Only documented read operations
   are reachable. Authentication is supplied externally. Preserve source endpoint,
   API version, identity kind, coverage and granted permission names without values.
5. Model observed evidence losslessly and tenant-scoped. Keep configuration, access
   control and telemetry as separate evidence dimensions. Empty, denied, unsupported,
   unlicensed, partial and failed are different states and never imply compliance.
6. Name the consumer before collecting a field: inventory/report, Assessment,
   comparison or a rule with an attributed normative basis. A convenient field is
   not by itself a defensible rule.
7. Expose the capability through the installed CLI and JSON, Markdown and HTML where
   the resource is reportable. Include it in Assessment/RunSet and comparison when
   meaningful. A hidden module is not delivery.
8. Test with synthetic fixtures: happy path, empty, `401`, `403`, unsupported or
   unlicensed, pagination, `429`/`Retry-After`, partial later page, malformed response,
   unknown future values, two-tenant isolation, provenance, manifest, installed wheel
   and a negative proof that the principal safety contract can fail.
9. Perform authorised read-only live observation when authentication, permission and
   licence already exist. Keep all live values ephemeral and publish only sanitised
   state. Never turn live observation into a prerequisite for deterministic tests.
10. Update the owning public contract, CLI help and external-source register. Do not
   publish tenant identifiers, private consumer information, commercial strategy or
   copied vendor prose.
11. Run focused tests while iterating, then the complete Engine release contract once
    the delta is stable. Do not repeat a green full gate without a changed affected
    input. Shut down build servers after heavy runs and run only one heavy gate at a
    time.
12. Record branch, head SHA, exact checks, sanitised evidence, exclusions and any
    local blocker in the PR. Reach `QA_READY`, then immediately select the next queue
    item. The Executor does not merge.

### Localised blockers

A missing external prerequisite blocks only the affected live proof or conclusion,
not fixtures, implementation, reports, tests, PR delivery or the next accepted slice.
Use one exact durable state:

- `BLOCKED_OWNER_AUTH_CONFIG` — no existing authentication path;
- `BLOCKED_OWNER_CONSENT_<PERMISSION>` — the exact documented read permission is absent;
- `BLOCKED_EXTERNAL_LICENSE_<SERVICE>` — the tenant lacks the required licence;
- `BLOCKED_EXTERNAL_API_<SURFACE>` — the official service is unavailable or failing;
- `BLOCKED_OWNER_BETA_API_<SURFACE>` — only a beta contract exists and adopting it
  changes the public stability promise;
- `BLOCKED_NORMATIVE_BASIS_<CONCLUSION>` — evidence is collectable but no authoritative
  basis supports the proposed conclusion.

Record the blocker in the PR and continue all unaffected work. Call the Auditor only
for an unresolved authority contradiction, a new write operation, customer-data risk,
public API break or product meaning that cannot be settled by the repository owner
contracts and current official sources. The Auditor answers governance questions; it
does not implement the slice.

## Accepted execution queue

The owner accepted this entire ordered queue on 2026-08-17. The first ten items are
the value-first wave and retain their exact order. All later items are also accepted
and continue automatically. An item includes only what official, supported contracts
can prove; unsupported sub-surfaces receive an exact local blocker rather than an
invented implementation.

### Wave 1 — highest-value surfaces

#### 1. `IDENTITY-CA-001` — Conditional Access

Use the detailed contract above: Conditional Access policies, named locations,
Security Defaults and referenced authentication strengths. Do not absorb the later
Identity cards.

#### 2. `IDENTITY-APPS-001` — applications and enterprise applications

Inventory app registrations and service principals, including ownership, publisher,
verified-publisher state, sign-in audience, credential metadata without secret
material, service-principal enablement and assignment requirements. Resolve references
between applications and enterprise applications. Use current Microsoft Graph v1.0
directory surfaces and independently verify the least read permissions. Consume the
result in inventory, Assessment, reports and comparison. Do not add/delete credentials,
grant consent or change applications.

#### 3. `IDENTITY-OAUTH-001` — OAuth consent and app-role grants

Collect `oauth2PermissionGrants` and applicable app-role assignments through their
current official Graph surfaces. Resolve client, resource, principal, scope/app role,
consent type and expiry where the contract supplies them, using `IDENTITY-APPS-001`
resources rather than recollecting directory objects. Distinguish delegated consent,
application permission and assignment. Provide inventory, Assessment, report,
comparison and only rules with an attributed Microsoft basis. Never grant or revoke
consent.

#### 4. `EXO-MAILFLOW-001` — Exchange mail flow

Audit and implement the supported read-only Exchange Online path for accepted domains,
remote domains, transport rules, inbound/outbound connectors and organisation-level
SMTP AUTH or legacy-auth settings where officially available. Preserve rule order,
enabled state and conditions/actions without exposing message or address data. Record
PowerShell module/version and required roles separately from Graph permissions. Provide
inventory, Assessment, reports and comparison. Do not change mail flow or send mail.

#### 5. `SPO-EXTERNAL-001` — SharePoint external sharing

Reuse the existing tenant-sharing and site-sharing collectors. Measure and extend only
verified gaps required to explain effective external sharing: tenant/site capability,
default link behaviour, anonymous-link availability and external-user exposure where a
supported read surface exists. Preserve tenant-versus-site precedence and `unknown`
when link usage cannot be observed. Add rules only from explicit Microsoft limits or
guidance. Test the two authorised SharePoint host forms without publishing live data.

#### 6. `SPO-SITES-001` — SharePoint and OneDrive site inventory

Reuse the current site inventory and classification resources. Add only verified,
consumer-backed gaps among owners, storage quota/usage, sensitivity label assignment,
versioning and lifecycle metadata supported by the chosen API. Represent OneDrive and
SharePoint site types explicitly. Avoid content enumeration and personal data. Prove
pagination, duplicate/canonical URL handling, inaccessible sites and comparison.

#### 7. `TEAMS-ACCESS-001` — external and guest access

Audit Microsoft Graph and Teams PowerShell ownership before choosing a path. Collect
tenant external-access, guest-access and team-creation governance settings available
through supported read contracts. Do not infer policy enforcement from membership or
guest presence. Record required roles, licences and PowerShell versions. Provide
inventory, Assessment, reports and comparison; never create a team or change policy.

#### 8. `INTUNE-COMPLIANCE-001` — compliance and device posture

Collect compliance policies, assignment scope, device-compliance summaries, enrolment
restrictions and a privacy-minimised device inventory through current Microsoft Graph
device-management contracts. Verify Intune licence and permission requirements and
gate every beta-only dependency explicitly. Keep policy configuration separate from
device evaluation. Do not collect unnecessary user/device identifiers or perform any
device action.

#### 9. `DEFENDER-SCORE-001` — Microsoft Secure Score

Collect the supported Secure Score control profiles, score snapshots and related
recommendations with current security API permissions and retention semantics. Label
scores as Microsoft projections: they never replace Engine evidence, provenance or
rules. Preserve unavailable products and licensing gaps. Provide trend/comparison and
reports without claiming that a score proves compliance. Do not update control state.

#### 10. `PURVIEW-LABELS-001` — sensitivity-label governance

Audit supported Microsoft Graph and Purview PowerShell read paths for label definitions,
publication/policy state and auto-labelling configuration. Keep tenant label governance
separate from existing SharePoint label assignment. Record security/compliance roles,
licence and beta dependencies. Provide inventory, Assessment, reports and comparison.
Do not publish labels, label content or change policies.

### Wave 2 — Identity completion

#### 11. `IDENTITY-AUTH-001`

Authentication-method policy, method configurations, registration/capability reporting
and MFA registration coverage. Aggregate privacy-sensitive user results by default;
retain no user identity unless an existing public contract explicitly requires it.
Separate policy enabled from user registered and capable. Include Security Defaults
only by reference to `IDENTITY-CA-001`.

#### 12. `IDENTITY-PRIV-001`

Directory roles, active and eligible assignments, PIM policy/configuration,
administrative units and declared emergency-access-account criteria. Never identify a
break-glass account by display name or guesswork: report configured evidence or
`not established`. Separate standing privilege, eligibility and PIM elevation history.

#### 13. `IDENTITY-XTENANT-001`

Cross-tenant access defaults and partner overrides, tenant restrictions, external
collaboration settings and B2B/B2C identity configuration supported by current APIs.
Do not enumerate external people unless essential and contractually owned; prefer
configuration and aggregate evidence.

#### 14. `IDENTITY-RISK-001`

Risky-user, risky-sign-in and sign-in-summary telemetry. Record licence, retention,
delay and permission limits; use bounded, privacy-minimised time windows. Telemetry is
not configuration. No identity names, IP addresses or raw sign-in events enter public
fixtures or durable evidence.

### Wave 3 — Exchange Online completion

#### 15. `EXO-PROTECTION-001`

Anti-spam, anti-phishing, Safe Attachments and Safe Links policy configuration,
including priority and assignment where supported. Preserve Microsoft-managed defaults
and unsupported licence states. Never submit or detonate content.

#### 16. `EXO-MAILBOX-001`

Mailbox forwarding, mailbox permission exposure, shared-mailbox posture and per-mailbox
SMTP AUTH state. Default output is aggregate/privacy-minimised; access to individual
mailbox identity requires an existing public consumer contract. No mailbox content or
addresses in fixtures/evidence.

#### 17. `EXO-DOMAIN-AUTH-001`

DKIM configuration plus observed DMARC and SPF DNS records for accepted domains.
Separate Exchange configuration, DNS observation and normative conclusion. Bound DNS
timeouts and preserve indeterminate results; never alter DNS.

### Wave 4 — SharePoint and OneDrive completion

#### 18. `SPO-CONTROLS-001`

Idle-session controls, restricted access control, tenant/site default-link settings and
site classification governance. Reuse earlier sharing and site evidence and model
effective precedence without duplicating collectors.

#### 19. `SPO-LIFECYCLE-001`

Versioning, storage quotas and supported site/OneDrive lifecycle controls. Distinguish
configured policy, current state and observed usage; do not inspect file content or
invent a lifecycle conclusion from age alone.

### Wave 5 — Teams completion

#### 20. `TEAMS-POLICIES-001`

Messaging, meeting and recording policy configuration and assignment coverage through
supported read surfaces. Separate global defaults, group/user assignment and effective
policy where Microsoft exposes it. Collect no meeting/chat content.

#### 21. `TEAMS-APPS-CHANNELS-001`

App permission/setup governance, third-party app availability and aggregate private/
shared-channel governance. Do not enumerate messages or expose team/channel names.

### Wave 6 — Intune completion

#### 22. `INTUNE-CONFIG-001`

Configuration profiles, Windows Update rings, BitLocker, Defender and ASR policy
configuration plus assignment coverage. Preserve platform/type-specific settings and
unknown future values. Never change or sync a device.

#### 23. `INTUNE-AUTOPILOT-001`

Device enrolment and Autopilot profile/deployment governance. Reuse device inventory,
minimise hardware identifiers and separate registered, assigned and deployed states.

### Wave 7 — Defender completion

#### 24. `DEFENDER-OPERATIONS-001`

Incidents, alerts, exposure recommendations, TVM recommendations and aggregate email,
endpoint, ASR and identity-protection posture through licensed supported APIs. Use
bounded windows and privacy-minimised evidence. Never close incidents or change
remediation state.

### Wave 8 — Purview completion

#### 25. `PURVIEW-DLP-RETENTION-001`

DLP, retention, data-lifecycle and auto-labelling policy configuration, publication and
assignment. Collect policy metadata, not protected content. Distinguish configured,
published and enforced where the API permits.

#### 26. `PURVIEW-INVESTIGATION-001`

Inventory-only governance for Insider Risk and eDiscovery cases/settings through
supported, least-privilege read contracts. Do not collect case content, custodians or
communications. If privacy-safe inventory has no defensible consumer, close it as
`BLOCKED_NORMATIVE_BASIS` rather than widening collection.

### Wave 9 — tenant platform

#### 27. `TENANT-ORG-001`

Licences/subscribed SKUs, verified domains, organisation settings, usage-location
coverage, company-branding configuration and administrative-role coverage. Reuse
Identity role evidence. Do not expose addresses, contact data or branding assets.

#### 28. `TENANT-HEALTH-001`

Service-health and Message Center summaries with bounded time windows, pagination and
retention. Treat both as operational telemetry, not tenant configuration or compliance.
Do not reproduce message bodies when identifiers and status suffice.

### Wave 10 — Power Platform

#### 29. `POWER-INVENTORY-001`

Environments, connectors and privacy-minimised Power Apps/Power Automate inventory.
Record Dataverse/admin API licence and role requirements. Do not execute flows or read
business records.

#### 30. `POWER-GOVERNANCE-001`

DLP policies, managed-environment configuration and tenant-isolation settings with
environment/connector assignment resolution. Never modify environments or policies.

### Wave 11 — Copilot governance

#### 31. `COPILOT-READINESS-001`

Copilot licence allocation aggregates, supported settings, restricted SharePoint
governance and documented semantic-index readiness evidence. Reuse SharePoint sharing,
site and label resources. Do not invent a readiness score or inspect prompts/content.

#### 32. `COPILOT-PLUGINS-001`

Supported plugin/agent governance and oversharing indicators derived from already
owned permission/sharing evidence. Keep configured availability separate from observed
use. Never enable, disable or invoke a plugin or agent.

## Programme completion

The queue is complete only when every card is either `QA_READY` with the common
vertical contract satisfied or carries a precisely scoped owner/external blocker that
cannot be resolved inside repository authority. No P0/P1 contract defect, silent
permission gap, inaccessible consumer, untested installed-wheel path or undocumented
partial state may remain. At that point the Executor records one sanitised programme
index linking the PR evidence for all completed cards and returns it to the Auditor for
release-governance review. This is not merge or deployment authority.
