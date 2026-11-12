# Governance report: Archive Store

- Resource: `contoso,site,archive-store` (site)
- Collected: 2026-08-06T09:00:00Z by `spo-collector` 0.3.0
- Source: SharePoint Online via PnP.PowerShell / SharePoint Admin
- **Tenant: `contoso.sharepoint.com`, as requested.** The address this collection was pointed at. Nothing read the directory the session was operating in, so this is what was asked for rather than what was observed.
- **Identity: Application.** This assessment reflects what the configured application was permitted to read, by tenant-granted application permissions. Its reach is not limited to what any one person can see.
- Scopes: Sites.Read.All

## Attention

**Part of this could not be answered, so the report describes less than the resource.**

- 15 finding(s) reached no answer

## Summary

16 rules evaluated. **1 produced an answer.**

| Outcome | Count |
|---|---|
| Fail | 1 |
| Invalid evidence | 0 |
| Error | 0 |
| Unknown | 15 |
| Pass | 0 |
| Not applicable | 0 |

15 rules could not be decided. That is not compliance: missing evidence is a fact about collection, not about the resource.

## Fail

### SPO-SITE-003 v1.0

The site uses 24100 MB of 25600 MB, which is 94 per cent of its quota. At this rate the next upload to fail will be somebody else's.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `site.storage_limit_set` = true, `site.storage_quota_mb` = 25600, `site.storage_used_mb` = 24100, `site.storage_used_percent` = 94

**What to do:** Raise the quota, or move content out. Which one is right depends on whether the site is growing because it is being used or because nothing has ever been removed from it, and that is a question the numbers here do not answer.

## Unknown

### SPO-ACTIVITY-001 v1.0

When a person last changed something on this site was not established, so how long it has been is not known. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: low
- Evidence: `activity.changeable` = <missing>, `activity.days_since_user_change` = <missing>

### SPO-CLASS-001 v1.0

Whether this site carries a label or a classification was not established. Neither property could be read, so the site may well be labelled. This is not a pass.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: low
- Evidence: `classification.classified` = <missing>
- Source: [Secure by default with Microsoft Purview, Step 3: expand to your entire Microsoft 365 data estate](https://learn.microsoft.com/purview/deploymentmodels/depmod-secure-by-default-step3) — checked 2026-08-06
- Source: [Use sensitivity labels to protect collaborative workspaces (groups and sites)](https://learn.microsoft.com/purview/sensitivity-labels-teams-groups-sites) — checked 2026-08-06

### SPO-CLASS-002 v1.0

Whether the label on this site resolves to a name was not established, because the label itself was not read. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: low
- Evidence: `classification.label_applied` = <missing>, `classification.label_resolved` = <missing>
- Source: [Use sensitivity labels to protect collaborative workspaces (groups and sites)](https://learn.microsoft.com/purview/sensitivity-labels-teams-groups-sites) — checked 2026-08-06

### SPO-CLASS-003 v1.0

Whether this group-connected site carries a sensitivity label was not established. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `classification.group_connected` = <missing>, `classification.label_applied` = <missing>
- Source: [Use sensitivity labels to protect collaborative workspaces (groups and sites)](https://learn.microsoft.com/purview/sensitivity-labels-teams-groups-sites) — checked 2026-08-06
- Source: [Control external access to resources in Microsoft Entra ID with sensitivity labels](https://learn.microsoft.com/entra/architecture/8-secure-access-sensitivity-labels) — checked 2026-08-06

### SPO-CLASS-004 v1.0

Whether a sensitivity label sits behind this site's classification string was not read. The evidence beside this finding says why. This is not a pass.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: low
- Evidence: `classification.classification_set` = <missing>, `classification.label_applied` = <missing>
- Source: [SharePoint "modern" sites classification](https://learn.microsoft.com/sharepoint/dev/solution-guidance/modern-experience-site-classification) — checked 2026-08-11
- Source: [Use sensitivity labels to protect collaborative workspaces](https://learn.microsoft.com/purview/sensitivity-labels-teams-groups-sites) — checked 2026-08-11

### SPO-MODERN-001 v1.0

The enabled features of this web were not read, so whether the classic publishing infrastructure is on is not known. This is not a pass.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: low
- Evidence: `web.web_feature_ids` = <missing>
- Source: [Moving from publishing sites to communication sites](https://learn.microsoft.com/sharepoint/publishing-sites-classic-to-modern-experience) — checked 2026-08-06
- Source: [SPMT supported SharePoint site features, feature identifiers](https://learn.microsoft.com/sharepointmigration/spmt-supported-site-features) — checked 2026-08-06

### SPO-MODERN-003 v1.0

The master page of this site was not read, so whether it is a provided one is not known. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: low
- Evidence: `web.custom_master_page_file` = <missing>

### SPO-MODERN-004 v1.0

The alternate stylesheet setting was not read, so whether one is loaded is not known. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: low
- Evidence: `web.alternate_css_url` = <missing>

### SPO-SCRIPT-001 v1.0

The custom script setting was not read, so whether this site permits it is not known. This is not a pass: the setting is returned by a tenant-scoped read, and a run that did not make one has established nothing about it.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: medium
- Evidence: `customization.custom_script_denied` = <missing>
- Source: [Security considerations of allowing custom script](https://learn.microsoft.com/sharepoint/security-considerations-of-allowing-custom-script) — checked 2026-08-22
- Source: [Allow or prevent custom script](https://learn.microsoft.com/sharepoint/allow-or-prevent-custom-script) — checked 2026-08-22
- Source: [MC1117115. Updates to custom scripting in sites and Classic Publishing site creation. Custom scripting disabled by default on classic publishing sites from 15 September 2025; the tenant-level opt-out command retired on 15 March 2026. A public mirror of the tenant Message Center, which is the primary and is tenant-scoped.
](https://mc.merill.net/message/MC1117115) — checked 2026-08-22

### SPO-SHARE-001 v1.0

The sharing capability of this site was not read, so whether it permits Anyone links is not known. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `sharing.capability` = <missing>
- Source: [Manage sharing settings for SharePoint and OneDrive, external sharing options](https://learn.microsoft.com/sharepoint/turn-external-sharing-on-or-off) — checked 2026-08-06
- Source: [Share within Microsoft OneDrive and SharePoint, sharable links overview](https://learn.microsoft.com/microsoft-365/education/guide/2-baseline/applications/baseline-apps-odsp-sharing) — checked 2026-08-06

### SPO-SHARE-002 v1.0

What a person gets when they press Share and change nothing is not settled here: either the setting was not read, or the site sets no default of its own and follows a tenant setting this collection did not read. The evidence beside this finding says which. This is not a pass.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: medium
- Evidence: `sharing.capability` = <missing>, `sharing.effective_default_link_type` = <missing>
- Source: [Change the default sharing link type for a site](https://learn.microsoft.com/sharepoint/change-default-sharing-link) — checked 2026-08-06

### SPO-SHARE-005 v1.0

What the default link lets its holder do is not settled here: the setting was not read. The evidence beside this finding says why. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `sharing.default_link_permission` = <missing>
- Source: [Change the default sharing link type for a site](https://learn.microsoft.com/sharepoint/change-default-sharing-link) — checked 2026-08-11
- Source: [Plan sharing and collaboration options in SharePoint and OneDrive](https://learn.microsoft.com/sharepoint/collaboration-options) — checked 2026-08-11

### SPO-SITE-001 v1.1

The owner count cannot establish whether this site has two administrators: either a group among the owners was not expanded, or the owners could not be read.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `owners.count` = <missing>

### SPO-SITE-002 v1.0

The administrators of this site were not read, so whether any of them is an individual account is not known. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: low
- Evidence: `owners.direct_count` = <missing>

### SPO-SPFX-001 v1.0

Whether any solution is behind the version the catalog holds is not known: either the catalog was not read, or it was read and no solution in it reports an installed version to compare against. The evidence beside this finding says which. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: low
- Evidence: `spfx.upgradable_count` = <missing>
