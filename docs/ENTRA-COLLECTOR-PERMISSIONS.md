# Permissions for the Microsoft Entra collectors

**Nothing here is granted, requested or consented.** This is the preparation an
owner reads before deciding whether a collector may be pointed at a tenant.
The `guests` and `applications` collectors exist. Each read one directory on
11 November 2026, after its owner consented to `User.Read.All` and
`Application.Read.All` at an interactive sign-in for that purpose. A
permission appearing in a catalogue is not a reason to ask for it, and holding
one is not authorization to audit a service.

Checked against the Microsoft Graph v1.0 reference on 11 November 2026. A cell
that was not read from the reference says so.

| Operation | Least privileged scope | Delegated / application | Role the signed-in person needs | Consent | Alternative |
|---|---|---|---|---|---|
| Guests: `GET /users?$filter=userType eq 'Guest'` | `User.Read.All`. `User.ReadBasic.All` is listed first for `GET /users`, and whether it returns `userType` is not established | both; `User.Read.All` is the least application permission | not established for this filter | administrator | none found |
| Applications: `GET /applications`, with `passwordCredentials` and `keyCredentials` | `Application.Read.All` | both | Directory Readers or Global Reader read standard properties; a member with default permissions is also listed | administrator | none needed |
| Service principals: `GET /servicePrincipals` | not yet established: next measurement is the `serviceprincipal-list` reference. Its owners relationship takes `Application.Read.All` | — | — | — | — |
| Delegated grants: `GET /oauth2PermissionGrants` | `Directory.Read.All`, which is the least the reference offers and is broad | both | Global Reader or Directory Readers | administrator | none: no narrower read scope is documented |
| Microsoft 365 groups, their owners and members: `GET /groups`, `/groups/{id}/owners`, `/groups/{id}/members` | `GroupMember.Read.All`, the least for owners and one that also lists groups and reads memberships. `GroupMember.ReadBasic.All` is less for members alone and does not read owners. The reference lists a write scope as the least for `GET /groups`, which this engine does not ask for | both | a member with default permissions, or Directory Readers | administrator | `Directory.Read.All`, wider and not needed |
| Role assignments | not yet established: next measurement is the `rbacapplication-list-roleassignments` reference | — | — | — | — |
| Conditional Access policies | `Policy.Read.All`, already used by the `conditional-access` collector | application in the recorded run | recorded with that collector | administrator | — |

## What this means for the composed scenarios

- **External access** needs guests, so `User.Read.All`. The collector exists
  and has read one directory. Without guest evidence the scenario reports
  what sites permit and says that guests were not read.
- **Application exposure** needs `Application.Read.All` and, for what was
  consented, `Directory.Read.All`. The second is the widest read in this table
  and is the one to decide on deliberately.
- **Ownership** reads the groups row above: the collector exists and read one
  directory on 12 November 2026, after its owner consented to
  `GroupMember.Read.All` at an interactive sign-in for that purpose.

## How a decision is asked for

One collector, one scope, one tenant, named in the request, immediately before
the consent. The application registered for the command line today holds
SharePoint `AllSites.FullControl` and Microsoft Graph `User.Read`, delegated,
and nothing in this table.
