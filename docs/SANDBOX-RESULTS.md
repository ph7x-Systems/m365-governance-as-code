# Sandbox validation

Run against a sandbox tenant on 2026-08-08 16:10 UTC, interactive and read-only.
The tenant is not named here: this repository is public, and a host name is an
identifier whether or not it is data.

## 1. Enumeration against identity

Compared 5 sites, both ways.

The site addresses are not reproduced: a URL is an identifier whether or not it
is data, and the finding is the disagreement rather than where it happened.

| Site | Quota | Used | Sharing, enumerated / read directly | Agrees |
|---|---|---|---|---|
| 1 | same | same | `Disabled` / `ExternalUserAndGuestSharing` | **NO** |
| 2 | same | same | `ExternalUserAndGuestSharing` / same | yes |
| 3 | same | same | `Disabled` / same | yes |
| 4 | same | same | `ExternalUserSharingOnly` / same | yes |
| 5 | same | same | `ExternalUserSharingOnly` / same | yes |

**1 of 5 diverged.** The cause is documented rather than deduced: `Get-SPOSite` states that filtered enumeration does not populate `SharingCapability` and may return a default value, and `Disabled` is the enum's default. The enumeration path stops being evidence for the twenty-two properties on that list. See `COLLECTION-PATH-AUDIT.md`.

## 2. TenantSharing, first run against a tenant

The three properties the collector reads and the two rules evaluate all
returned a value, each one a member of its documented enum. **Read here to
prove the call returns them at all**, which a fixture cannot. The values
themselves are that tenant's configuration and are not reproduced; the enums
they came from are documented by Microsoft and are in the rules.

## 3. The two articles

`read-tenant-default-sharing-link-type` and `read-anyone-link-permissions` said `tested_with: [PnP.PowerShell 3.3.0]` and deliberately not `SharePoint Online`.

**Observed, so both now say `SharePoint Online` as well.** The enum values above are what a reader will see.

## 4. SPFx API permissions

Could not be read: Forbidden (403): Insufficient privileges to complete the operation.

**That is an answer.** A refusal is a coverage fact, not a gap in this report.

## Fixture

Wrote `src/m365_governance/data/fixtures/sharepoint/tenant-sharing-observed-20260808.json`, in the shape this tenant returned.

**The tenant identity is replaced**, deliberately and not as an oversight: the shape is the finding, the tenant is not. What is real in it is the arrangement of states and the values the enum actually takes.

---

**Nothing above is a verdict.** These are observations and coverage. What any of it means is the engine's answer, from this evidence.
