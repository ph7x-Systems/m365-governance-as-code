# IDENTITY-CA-001 — source and collection-path audit

**Read 2026-08-17 from Microsoft Learn, against `graph-rest-1.0`.** Every row
below was opened, not remembered. Re-open the pages before writing the
collector: this file records what the contract said on that date and is
evidence of intent rather than proof of runtime behaviour.

> **Nothing here has been observed against a tenant.** This audit establishes
> what Microsoft documents. What the API returns is a separate question, and
> the entries marked `needs-tenant-validation` say so.

## Source authority and canonical location

The documentation remains at the publisher; this repository records the exact
authority and links rather than copying it:

| Question | Canonical documentation | Location |
|---|---|---|
| Microsoft Graph operations, permissions, resource semantics and national-cloud support | Microsoft Learn — Microsoft Graph v1.0 | the exact `learn.microsoft.com/graph/api/...` operation and resource pages cited in each section below |
| PnP.PowerShell cmdlet existence, parameter sets, connection requirements and return shape | PnP.PowerShell documentation owned by `pnp/powershell`, fixed to the version used by the Engine | <https://github.com/pnp/powershell/tree/v3.3.0/documentation> |
| `Get-PnPTenantId` in the fixed PnP version | the cmdlet page in the same tagged documentation | <https://github.com/pnp/powershell/blob/v3.3.0/documentation/Get-PnPTenantId.md> |

Microsoft Learn is not the authority for PnP.PowerShell. The current PnP website may
describe a newer release, so reproducible implementation questions use the tagged
repository documentation. Runtime output remains evidence of one run, not vendor
documentation.

## 1. Endpoints and response types

| Surface | Read operation | Response type |
|---|---|---|
| Conditional Access policies | `GET /v1.0/identity/conditionalAccess/policies` | collection of `conditionalAccessPolicy` |
| Named locations | `GET /v1.0/identity/conditionalAccess/namedLocations` | collection of `namedLocation` |
| Security Defaults | `GET /v1.0/policies/identitySecurityDefaultsEnforcementPolicy` | single `identitySecurityDefaultsEnforcementPolicy` |

**Authentication strengths are not a fourth call.** The policy response embeds
`grantControls.authenticationStrength` as a full object — `id`, `displayName`,
`policyType`, `requirementsSatisfied`, `allowedCombinations`,
`combinationConfigurations` — so a strength referenced by a policy arrives with
that policy. This removes the fourth endpoint the slice contemplated, and with
it the separate permission question it raised.

Sources:

- <https://learn.microsoft.com/graph/api/conditionalaccessroot-list-policies?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/conditionalaccessroot-list-namedlocations?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/identitysecuritydefaultsenforcementpolicy-get?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/resources/conditionalaccesspolicy?view=graph-rest-1.0>

## 2. Least privilege, delegated and application, separately

| Surface | Delegated (work or school) | Application |
|---|---|---|
| Policies | `Policy.Read.All` | `Policy.Read.All` |
| Named locations | `Policy.Read.All` | `Policy.Read.All` |
| Security Defaults | `Policy.Read.All` | `Policy.Read.All` |

**One scope covers the whole slice**, and in both identity kinds. Microsoft
records *"Not available"* under higher-privileged for all three, so there is no
broader alternative to fall back to and no reason to request one.

**Personal Microsoft accounts are not supported** on any of the three. A
delegated session on a personal account is not a partial answer here; it is a
surface that does not exist.

**Delegated access additionally needs a directory role.** Microsoft names the
built-in roles that grant only the least privilege necessary:

```text
Global Secure Access Administrator   (standard properties)
Security Reader                      (standard properties)
Security Administrator               (standard properties)
Global Reader
Conditional Access Administrator
```

That list is identical for policies and named locations. **A delegated identity
holding `Policy.Read.All` and none of those roles is a documented failure mode
this collector must distinguish from an empty tenant.**

## 3. National clouds

All three surfaces are documented as available in Global service, US Government
L4, US Government L5 (DOD) and China operated by 21Vianet.

**The endpoint host differs per cloud** and the provider must take it as
configuration rather than hard-coding `graph.microsoft.com`. Availability of the
operation is not availability at one address.

## 4. Licensing

Microsoft states no licence prerequisite on any of the three operation pages.

**`not established`, deliberately.** Conditional Access itself has licensing
requirements documented elsewhere in Entra, and the absence of a statement on an
API page is not a statement of absence. A tenant without the required licence may
answer differently, and this collector must not read that difference as a
governance finding. Recorded as `needs-tenant-validation`.

## 5. Pagination and query parameters

| Surface | Documented OData parameters |
|---|---|
| Policies | `$skip`, `$top`, `$count`, `$filter`, `$orderby`, `$select` |
| Named locations | `$count`, `$filter`, `$orderby`, `$select`, `$skip`, `$top` |
| Security Defaults | `$select` only |

**Follow `@odata.nextLink` and never construct a page URL.** The examples show
`@odata.context` on every response; the collector treats the absence of a next
link as the end of the collection and nothing else.

**No `$select` in production collection.** The slice must record what the tenant
has, and a projection chosen by us decides in advance what a future rule may
read. Fields omitted unless selected are therefore not a risk this collector
takes on.

`needs-tenant-validation`: whether these collections page at all at real tenant
sizes, and what page size the service actually applies. The documentation does
not state a default.

## 6. Throttling, transient failure, retry

**Not documented on any of the three operation pages.** Microsoft Graph's
throttling guidance is service-wide rather than per-operation.

The provider therefore implements the general contract — honour `Retry-After` on
`429`, bound the number of retries, and stop rather than loop — and records the
exhaustion as an unavailable area with its reason. **A collection that gave up
is `partial` with a stated cause and never an empty tenant.**

`needs-tenant-validation`: the actual limits for this surface.

## 7. What each answer means

| Answer | Meaning | Never |
|---|---|---|
| `200` with `value: []` | The tenant has none of this object | a policy that could not be read |
| `401` | The session is not authenticated | a tenant with no policies |
| `403` | Authenticated and not permitted: missing `Policy.Read.All`, or a delegated identity without one of the roles in §2 | a compliant tenant |
| `404` | The resource path does not exist in this cloud or version | an absent policy |
| `429` | Throttled | anything about the tenant |

**The distinction that matters most.** An empty collection and a denied read
produce the same shape in a naive collector: nothing. They are opposite facts.
`coverage.unavailable` carries the reason, and a rule over a denied read answers
`unknown`.

## 8. Evolvable enums

`conditionalAccessPolicy` carries several evolvable enumerations, and Microsoft's
convention is that a client which has not opted in receives `unknownFutureValue`
in place of a member added after the client's opt-in point.

**A value this engine does not know is preserved verbatim and never mapped.**
Neither to a default, nor to `pass`, nor to an absence. An unknown state on a
policy is exactly the case where a rule must answer `unknown`, and a collector
that normalised it would remove the reader's only signal that the product has
moved.

The slice does not opt in to preview enum members. Opting in is a decision about
what the engine claims to understand.

## 9. Fields that need more than the read permission

None documented for these three operations. Both roles listed in §2 are
annotated *"read standard properties"*, which implies a non-standard set exists;
Microsoft does not enumerate it on these pages.

`needs-tenant-validation`: whether a Global Reader and a Conditional Access
Administrator observe the same policy document. **Until that is measured, a
field absent under one identity must not be recorded as absent from the tenant.**

## 10. Basis available for rules

Nothing on these pages is a `requirement` or a `documented-limit`: they describe
a read API, not a governance position. Any rule written on this evidence takes
its basis from a separate Microsoft document that states a position, cited on
the rule.

**No rule is created because a field exists.** An inventory that ships without a
rule names its report consumer and says why Microsoft offers no normative
conclusion, exactly as the `agents` slice does.

## 11. Identifiers this slice can and cannot resolve

**Carried as stable native IDs, unresolved:** users, groups, directory roles,
applications, service principals, terms of use, authentication context class
references.

**Resolvable within the slice:** named locations, because the slice collects
them; and authentication strengths, because the policy embeds them.

**Directory-wide inventory is out of scope**, and resolving a display name for
every excluded group would be exactly that. An unresolved reference keeps its
ID and states that it was not resolved, which is a smaller and truer claim than
a friendly label the collector had to go looking for.

## 12. What this audit changed in the slice contract

1. **Authentication strengths are not a separate endpoint.** They arrive
   embedded, so the fourth call and its unverified permission are removed.
2. **One permission covers everything:** `Policy.Read.All`, delegated and
   application. There is nothing to negotiate per surface.
3. **A delegated identity also needs a directory role**, and lacking one is a
   documented denial rather than an empty result. That is now a required test
   case.
4. **The endpoint host is configuration**, because all four national clouds are
   supported and none of them share an address.

## 13. Open, and blocking nothing

| Question | State |
|---|---|
| Licensing prerequisite for Conditional Access | `needs-tenant-validation` |
| Real pagination behaviour and page size | `needs-tenant-validation` |
| Throttling limits for this surface | `needs-tenant-validation` |
| Whether roles differ in the fields they return | `needs-tenant-validation` |

Each needs an authenticated read against a real tenant with `Policy.Read.All`,
which is owner-only. None of them blocks the provider, the fixtures, the
contracts, the rules or the tests, which is why the slice continues.

## 14. Live observation, 2026-08-17: `BLOCKED_OWNER_POLICY_READ_ALL`

**A session was opened against the authorised tenant and Graph was read.** The
tenant is not named here: this repository is public.

| Surface | Answer |
|---|---|
| `identity/conditionalAccess/policies` | `403` |
| `identity/conditionalAccess/namedLocations` | `403` |
| `policies/identitySecurityDefaultsEnforcementPolicy` | `403` |

```text
scopes granted:  AllSites.Read User.Read profile openid email
Policy.Read.All: absent
Graph's reason:  "required scopes are missing in the token"
```

**This is the case the provider exists for, observed rather than imagined.**
Three surfaces answered `403` and not one of them answered `200` with an empty
collection. A naive collector would have reported a tenant with no Conditional
Access policies, no named locations and no Security Defaults state — the
strongest possible governance conclusion, drawn from a permission nobody
granted.

The engine's answer is the opposite: `permission-denied` on all three,
`coverage.unavailable` carrying Graph's own sentence, and any rule over that
evidence answering `unknown`.

### What this settles, and what it does not

**Settled by a run:** the sign-in path works, `Get-PnPAccessToken
-ResourceTypeName Graph` returns a Graph token from the existing session, and
the token's `scp` claim is where the granted scopes actually are — which is
what the provider reads to record identity.

**Not settled, because a `403` reads nothing:** pagination behaviour, throttling
limits, whether roles differ in the fields they return, and the licensing
question. All four remain `needs-tenant-validation` from §13, unchanged.

### What unblocks it

`Policy.Read.All` consented for the application registration used above. The
application exists and authenticates; it holds `AllSites.Read` and nothing that
reaches identity. Granting a Graph permission is an owner action on the
directory, and this engine never requests consent.

**One thing learned at the owner's expense.** Two interactive sessions were
spent on client ids: one invented, one read from the wrong column. Both would
have been answered in three seconds without a browser, by asking the token
endpoint whether the application exists:

```bash
curl -s -X POST "https://login.microsoftonline.com/<tenant>/oauth2/v2.0/devicecode" \
  -d "client_id=<candidate>&scope=https%3A%2F%2Fgraph.microsoft.com%2F.default"
```

An application that exists returns a device code; one that does not returns
`AADSTS700016`. **Validate a client id there before spending a session on a
browser.**

## 15. Previously: `BLOCKED_OWNER_AUTH_CONFIG`

**Recorded 2026-08-17.** The slice's authentication precedence was walked
without printing any value:

```text
ENTRAID_APP_ID     absent
ENTRAID_CLIENT_ID  absent
AZURE_CLIENT_ID    absent
managed PnP session   none open
```

No authentication configuration exists on this machine, and the slice forbids
creating one. **This blocks live observation only.** The provider, fixtures,
contracts, rules, reports and tests continue against synthetic evidence, which
is what every other collector in this engine is built from.

### How a token reaches the provider, when one exists

Read from the PnP documentation at the pinned tag rather than assumed:

```powershell
Get-PnPAccessToken -ResourceTypeName Graph
```

`ResourceTypeName` accepts `Graph`, `SharePoint` and `ARM`, and defaults to
`Graph`. It requires an existing connection.

<https://github.com/pnp/powershell/blob/v3.3.0/documentation/Get-PnPAccessToken.md>

**This is why the provider never acquires authentication.** The operator opens
one session with the collector's existing interactive path, and the same
session yields the Graph token. Nothing new is consented, nothing is cached by
this engine, and the identity that reads Graph is the identity the operator
already signed in as.

### What unblocks it

An application registration **that exists in the tenant** and whose id is
supplied through the precedence above. A client id that does not exist in the
directory fails at the sign-in screen with `AADSTS700016`, which spends an
interactive session to learn something a token request would have said first.

Once a session opens, the remaining question is whether `Policy.Read.All` is
consented. If it is not, Graph answers `403`, the collector records
`permission-denied` with the reason, and that is
`BLOCKED_OWNER_POLICY_READ_ALL` — the second blocked state the slice
anticipates, and it costs no further interactive session to establish.

## 16. The answer matrix, and the contract gap it exposed

Every answer a caller can receive, what it means, and what it may never become.
All rows are covered offline by `tests/test_graph.py`; the live column records
which have also been seen against a real tenant.

| Answer | State | Never | Live |
|---|---|---|---|
| `200` with objects | complete, carried whole | reshaped or projected | not yet |
| `200` with `value: []` | complete, the tenant has none | a read that was denied | not yet |
| `401` | `missing` — the session is not valid | a permission problem | not yet |
| `403` | `permission-denied`, with Graph's own sentence | a compliant or empty tenant | **observed** |
| `404` | `not-supported` — this cloud or version | an absent policy | not yet |
| `429`, budget exhausted | `partial`, keeping what was read | absent data | not yet |
| `200` that is not JSON, or has no `value` | `invalid` | an empty tenant | not yet |
| no Graph token | refused before any request | an empty result | not yet |
| one page read, next refused | `partial` with items | `completed` | not yet |

### `401` and `403` were the same state, and that was a defect

Both mapped to `permission-denied`. They are different sentences: a `401` says
the session is not valid — expired, issued for another audience, never
established — and a `403` says a valid session was refused this surface.
**Reading the first as the second sends somebody to request a Graph permission
when what they needed was to sign in again.**

### The gap this leaves in the evidence contract

The evidence contract publishes four absent states:

```text
missing · not-supported · permission-denied · partial
```

**None of them means "not authenticated".** `401` is recorded as `missing` with
a detail that says so in words, which is the honest use of the vocabulary that
exists rather than borrowing the nearest word that fits.

Whether the evidence contract should gain a fifth state is a decision for the
Engine, and it costs an evidence contract version. It is recorded here rather
than settled: a collector that invented a state would be the second authority
on evidence semantics, which is the thing this repository refuses everywhere
else.

### What may not be claimed yet

> Conditional Access was successfully collected from a real tenant.

That sentence needs a `200` under `Policy.Read.All`. The negative live path is
proven; the positive live path is `needs-tenant-validation`, and it is the last
square rather than a blocker on the rest of the slice.

