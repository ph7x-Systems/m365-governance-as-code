# Governance report: Require multifactor authentication for administrators

- Resource: `aaaaaaaa-0000-4000-8000-000000000001` (conditional-access-policy)
- Collected: 2026-08-17T09:00:00Z by `graph-conditional-access` 1.0.0
- Source: Microsoft Entra ID via Microsoft Graph v1.0
- **Tenant: `contoso.sharepoint.com`, as requested.** The address this collection was pointed at. Nothing read the directory the session was operating in, so this is what was asked for rather than what was observed.
- **Identity: Application.** This assessment reflects what the configured application was permitted to read, by tenant-granted application permissions. Its reach is not limited to what any one person can see.
- Scopes: Policy.Read.All

## Attention

**Nothing is outside a documented requirement. Some findings are worth weighing.**

- 3 finding(s) were decided and are worth weighing

## Summary

3 rules evaluated. **3 produced an answer.**

| Outcome | Count |
|---|---|
| Fail | 2 |
| Invalid evidence | 0 |
| Error | 0 |
| Unknown | 0 |
| Pass | 1 |
| Not applicable | 0 |


## Fail

### CA-RECOVERY-001 v1.0

This policy includes all users and excludes no user, no group and no directory role. If it prevents sign-in for any reason, the accounts that would change it are subject to it, and recovery runs through Microsoft support rather than through an administrator.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: high
- Evidence: `conditional_access_policies.exclusions_declared` = 0, `conditional_access_policies.included_users` = ['All']
- Source: [Require multifactor authentication for all users](https://learn.microsoft.com/entra/identity/conditional-access/policy-all-users-mfa-strength) — checked 2026-08-23
- Source: [Manage emergency access accounts in Microsoft Entra ID](https://learn.microsoft.com/entra/identity/role-based-access-control/security-emergency-access) — checked 2026-08-23

**What to do:** Microsoft's documented answer is an emergency access account, excluded from this policy in advance and managed under the guidance for such accounts. A tenant whose recovery path is deliberately something else answers the same question differently, and the finding is the record of which one this is.

### CA-SCOPE-001 v1.0

This policy includes all users. Calls made by service principals are not blocked by it: Conditional Access policies scoped to users do not reach workload identities, and an application signing in on its own behalf is not subject to what this policy requires.

- Basis: **documented-guidance** — Microsoft recommends this; the product permits the alternative
- Severity: medium
- Evidence: `conditional_access_policies.included_users` = ['All']
- Source: [Require multifactor authentication for all users](https://learn.microsoft.com/entra/identity/conditional-access/policy-all-users-mfa-strength) — checked 2026-08-23
- Source: [Target resources in Conditional Access policy](https://learn.microsoft.com/entra/identity/conditional-access/concept-conditional-access-cloud-apps) — checked 2026-08-23

**What to do:** Where workload identities need the same treatment, Microsoft's named answer is Conditional Access for workload identities, which is a separate policy targeting service principals. Where they deliberately do not, the finding is the record of that decision rather than a fault to fix.

## Pass

### CA-STATE-001 v1.0

This policy is not in report-only mode.

- Basis: **convention** — widely held practice, not documented as a rule
- Severity: medium
- Evidence: `conditional_access_policies.policy_state` = enabled
- Source: [Analyze Conditional Access policy impact](https://learn.microsoft.com/entra/identity/conditional-access/concept-conditional-access-report-only) — checked 2026-08-23
- Source: [conditionalAccessPolicy resource type](https://learn.microsoft.com/graph/api/resources/conditionalaccesspolicy) — checked 2026-08-23

**This pass does not establish:** A POLICY THAT IS NOT REPORT-ONLY MAY STILL ENFORCE NOTHING. `disabled` is a separate state and this rule does not read it. A policy that is enabled may exclude every user it would otherwise apply to, apply to no application, or require a control that every sign-in already satisfies. This reads the state and nothing else, and a pass says only that the state is not the one Microsoft documents as not enforcing.
