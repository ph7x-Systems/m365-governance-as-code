# Governance report

- 1 resources observed
  by kind of resource, which is not an outcome:
  unknown         1

> **Run coverage: not established.** 1 resources are stored. The total number the identity was expected to reach was not recorded, so this run does not establish complete coverage.

> **Identity: delegated.** These runs saw what one person sees. Nothing here may be read as a tenant-wide statement.

## Summary

14 rule evaluations across 1 resources. **8 produced an answer.**

| Outcome | Count |
|---|---|
| Fail | 4 |
| Invalid evidence | 0 |
| Error | 0 |
| Unknown | 1 |
| Pass | 4 |
| Not applicable | 5 |

1 could not be decided. That is not compliance: missing evidence is a fact about collection, not about the resource.

## Findings

### All Company

- **Fail** · SPO-ACTIVITY-001 v1.0 · convention
  No person has changed anything on this site for 440 days. System processes have touched it since; a person has not.
- **Fail** · SPO-CLASS-001 v1.0 · documented-guidance
  This site carries neither a sensitivity label nor a classification string. Nothing recorded on it says what kind of content it holds.
- **Not applicable** · SPO-CLASS-002 — covered by SPO-CLASS-001.
- **Fail** · SPO-CLASS-003 v1.0 · convention
  This site is connected to a Microsoft 365 group and carries no sensitivity label. Privacy and external user access rest on the settings of the group itself, and nothing pins them. A classification string does not pin a group's access.
- **Not applicable** · SPO-CLASS-004 — covered by SPO-CLASS-001.
- **Unknown** · SPO-SITE-001 v1.1 · convention
  The owner count does not settle whether this site has two: either the owners were not collected, or a group among them was not expanded. The evidence beside this finding says which. This is not a pass.
- **Fail** · SPO-SITE-002 v1.0 · convention
  Every administrator of this site is a group. Nobody is named individually, so who can act is a question that has to be answered before it can be acted on.
