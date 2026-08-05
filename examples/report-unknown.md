# Governance report: Legal

- Resource: `contoso,site,legal` (site)
- Collected: 2026-08-05T14:02:11Z by `spo-collector` 0.1.0
- Source: SharePoint Online via Microsoft Graph v1.0
- Identity: application, scopes: Sites.Read.All
- **Not collected:**
  - `owners` — permission-denied: The identity lacks Sites.FullControl.All

## Summary

1 rule evaluated. **0 produced an answer.**

| Outcome | Count |
|---|---|
| Fail | 0 |
| Invalid evidence | 0 |
| Unknown | 1 |
| Error | 0 |
| Not applicable | 0 |
| Pass | 0 |

1 rule could not be decided. That is not compliance: missing evidence is a fact about collection, not about the resource.

## Unknown

### SPO-SITE-001 v1.0

The owners of this site were not collected, so the number is not known. This is not a pass.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `owners.count` = <permission-denied>
