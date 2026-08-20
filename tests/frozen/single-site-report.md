# Governance report

- 1 resource observed

> **Run coverage: not established.** 1 resource is stored. The total number the identity was expected to reach was not recorded, so this run does not establish complete coverage.

> **Identity: delegated.** These runs saw what one person sees. Nothing here may be read as a tenant-wide statement.

## Summary

14 rule evaluations across 1 resource.

| Outcome | Count |
|---|---|
| Fail | 4 |
| Unknown | 1 |
| Pass | 4 |
| Not applicable | 5 |

Undecided is not compliance: missing evidence is a fact about collection, not about the resource.

## Findings

### All Company

- **Fail** · SPO-ACTIVITY-001 v1.0 · convention
  No person has changed anything on this site for 440 days. System processes have touched it since; a person has not.
  **What to do:** Find out what it was for before deciding anything. The cheapest outcome is usually to archive it, which keeps the content and takes it out of every list somebody has to read; deleting is a decision that needs an owner, and a site in this state often no longer has one.
- **Fail** · SPO-CLASS-001 v1.0 · documented-guidance
  This site carries neither a sensitivity label nor a classification string. Nothing recorded on it says what kind of content it holds.
  **What to do:** Decide first whether the tenant is using container labels at all. If it is not, every site will fail this rule and the finding to act on is the tenant decision, not the site. If it is, the deployment model Microsoft publishes works outward from the sites that matter most rather than through the list in order, and this rule set can produce that list but cannot rank it.
- **Not applicable** · SPO-CLASS-002 — covered by SPO-CLASS-001.
- **Fail** · SPO-CLASS-003 v1.0 · convention
  This site is connected to a Microsoft 365 group and carries no sensitivity label. Privacy and external user access rest on the settings of the group itself, and nothing pins them. A classification string does not pin a group's access.
  **What to do:** Read the group settings before applying anything. A label sets privacy and external access and locks them, so applying one to a group that is currently configured differently changes the group. That is the point of it and it is also how a labelling exercise removes somebody's access on a Tuesday afternoon.
- **Not applicable** · SPO-CLASS-004 — covered by SPO-CLASS-001.
- **Unknown** · SPO-SITE-001 v1.1 · convention
  The owner count cannot establish whether this site has two administrators: either a group among the owners was not expanded, or the owners could not be read.
- **Fail** · SPO-SITE-002 v1.0 · convention
  Every administrator of this site is a group. Nobody is named individually, so who can act is a question that has to be answered before it can be acted on.
  **What to do:** Name at least one person alongside the groups, and tell them. The point is not the field: it is that somebody knows the site is theirs to decide about.
