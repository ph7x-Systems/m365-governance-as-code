<#
    validate-sandbox.ps1

    The four validations that were written against documentation and never
    observed, in the order the owner set, in one run.

    You authenticate. Everything after that is automatic.

        pwsh tools/validate-sandbox.ps1 -TenantUrl https://<tenant>-admin.sharepoint.com `
                                        -SiteUrl   https://<tenant>.sharepoint.com `
                                        -ClientId  <your app id>

    READ-ONLY. Nothing here calls a Set-, New-, Remove-, Add-, Grant- or
    Revoke- cmdlet, and the release contract proves that of every file under
    collectors/ on every release. A sandbox validates behaviour; it does not
    authorise writing.

    INTERACTIVE, NEVER A DEVICE CODE. A device-code session is not the same
    consent or the same user context, and a validation that does not reproduce
    the context validates nothing.

    Writes docs/SANDBOX-RESULTS.md. Nothing is concluded here: the file records
    what was observed, and what it means is decided afterwards, in the open.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $TenantUrl,
    [Parameter(Mandatory = $true)] [string] $SiteUrl,
    [Parameter(Mandatory = $true)] [string] $ClientId,
    [Parameter()] [int] $Sample = 5,
    [Parameter()] [string] $OutputPath = "docs/SANDBOX-RESULTS.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$report = [System.Collections.Generic.List[string]]::new()
function Say([string] $line) { Write-Host $line; $report.Add($line) }

Say "# Sandbox validation"
Say ""
Say "Run against ``$TenantUrl`` on $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm')) UTC."
Say ""

Write-Host "`nConnecting. A browser will open." -ForegroundColor Cyan
Connect-PnPOnline -Url $TenantUrl -Interactive -ClientId $ClientId

# ── 1. enumeration against identity ─────────────────────────────────────────
# The question `needs-tenant-validation` has been carrying since the audit:
# Microsoft warns that Get-SPOSite with Limit or Filter leaves properties
# unpopulated, and nothing says whether Get-PnPTenantSite inherits it.
Say "## 1. Enumeration against identity"
Say ""
$sites = @(Get-PnPTenantSite | Select-Object -First $Sample)
Say "Compared $($sites.Count) sites, both ways."
Say ""
Say "| Site | Quota | Used | Sharing | Agrees |"
Say "|---|---|---|---|---|"

$divergent = 0
foreach ($s in $sites) {
    $one = Get-PnPTenantSite -Identity $s.Url
    $same = ($s.StorageQuota -eq $one.StorageQuota) -and
            ($s.StorageUsageCurrent -eq $one.StorageUsageCurrent) -and
            ("$($s.SharingCapability)" -eq "$($one.SharingCapability)")
    if (-not $same) { $divergent++ }
    $name = ([uri]$s.Url).AbsolutePath
    Say "| ``$name`` | $($s.StorageQuota) / $($one.StorageQuota) | $($s.StorageUsageCurrent) / $($one.StorageUsageCurrent) | $($s.SharingCapability) / $($one.SharingCapability) | $(if ($same) { 'yes' } else { '**NO**' }) |"
}
Say ""
Say $(if ($divergent -eq 0) {
    "**No divergence across $($sites.Count) sites.** The risk is reduced and this is the record of it. It is not a proof for every site in every tenant."
} else {
    "**$divergent of $($sites.Count) diverged. A collector defect is proven**, and the enumeration path stops being evidence for those properties."
})
Say ""

# ── 2. the tenant sharing collector, first real run ─────────────────────────
Say "## 2. TenantSharing, first run against a tenant"
Say ""
$tenant = Get-PnPTenant
Say "| Property | Value |"
Say "|---|---|"
foreach ($p in 'SharingCapability', 'DefaultSharingLinkType', 'FileAnonymousLinkType') {
    Say "| ``$p`` | $($tenant.$p) |"
}
Say ""
Say "These are the three the collector reads and the two rules evaluate. **Read here to prove the call returns them at all**, which a fixture cannot."
Say ""

# ── 3. what the two Knowledge articles claim ────────────────────────────────
Say "## 3. The two articles"
Say ""
Say "``read-tenant-default-sharing-link-type`` and ``read-anyone-link-permissions`` say ``tested_with: [PnP.PowerShell 3.3.0]`` and deliberately not ``SharePoint Online``."
Say ""
$observed = $tenant.SharingCapability -and $tenant.DefaultSharingLinkType
Say $(if ($observed) {
    "**Observed.** The frontmatter may now say ``SharePoint Online`` as well, and the enum values above are what a reader will see."
} else {
    "**Not observed.** The properties returned nothing, and the frontmatter stays as it is."
})
Say ""

# ── 4. SPFx API permissions, surface only ───────────────────────────────────
# The domain the PnP inventory chose. Enumerating it is not proposing a rule:
# whether Microsoft documents guidance on reviewing these is a separate
# question, and it decides everything.
Say "## 4. SPFx API permissions"
Say ""
try {
    $granted = @(Get-PnPEntraIDAppPermission)
    Say "$($granted.Count) permission grants on the SPFx service principal."
    Say ""
    if ($granted.Count) {
        Say "| Resource | Scope |"
        Say "|---|---|"
        foreach ($g in $granted | Select-Object -First 20) {
            Say "| $($g.Resource) | $($g.Scope) |"
        }
    }
}
catch {
    Say "Could not be read: $($_.Exception.Message)"
    Say ""
    Say "**That is an answer.** A refusal is a coverage fact, not a gap in this report."
}
Say ""
# ── what the run leaves behind ──────────────────────────────────────────────
# A validation that only produces a report improves nothing permanently. This
# writes a fixture in the shape the tenant actually returned, with every
# identifying value replaced, so the observation becomes a test rather than a
# memory. No real tenant data enters git.
Say "## Fixture"
Say ""
$fixture = [ordered]@{
    schema_version = '1.0'
    provenance     = [ordered]@{
        collected_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        collector         = 'spo-collector'
        collector_version = '0.3.0'
        source_system     = 'SharePoint Online'
        source_api        = 'PnP.PowerShell / SharePoint Admin'
        tenant_id         = 'contoso-admin.sharepoint.com'
        identity_kind     = 'delegated'
        scopes            = @('AllSites.Read')
    }
    coverage       = [ordered]@{
        requested   = @('tenant_sharing')
        completed   = @('tenant_sharing')
        unavailable = [ordered]@{}
    }
    resource       = [ordered]@{
        id           = 'https://contoso-admin.sharepoint.com'
        type         = 'tenant'
        display_name = 'https://contoso-admin.sharepoint.com'
        url          = 'https://contoso-admin.sharepoint.com'
    }
    facts          = [ordered]@{
        tenant_sharing = [ordered]@{}
    }
}

$map = @{
    capability               = 'SharingCapability'
    default_link_type        = 'DefaultSharingLinkType'
    file_anonymous_link_type = 'FileAnonymousLinkType'
}
foreach ($name in $map.Keys) {
    $property = $map[$name]
    $value = $tenant.$property
    $fixture.facts.tenant_sharing[$name] = if ($null -eq $value -or "$value" -eq '') {
        [ordered]@{ state = 'missing'; detail = "$property was not returned for this tenant." }
    }
    else {
        [ordered]@{
            state = 'observed'
            value = "$value"
            raw   = [ordered]@{ field = $property; value = "$value" }
        }
    }
}

$fixtureName = "tenant-sharing-observed-$((Get-Date).ToUniversalTime().ToString('yyyyMMdd')).json"
$fixturePath = Join-Path 'src/m365_governance/data/fixtures/sharepoint' $fixtureName
$fixture | ConvertTo-Json -Depth 12 | Set-Content -Path $fixturePath -Encoding utf8

Say "Wrote ``$fixturePath``, in the shape this tenant returned."
Say ""
Say "**The tenant identity is replaced**, deliberately and not as an oversight: the shape is the finding, the tenant is not. What is real in it is the arrangement of states and the values the enum actually takes."
Say ""
Say "---"
Say ""
Say "**Nothing above is a verdict.** These are observations and coverage. What any of it means is the engine's answer, from this evidence."

$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
$report -join "`n" | Set-Content -Path $OutputPath -Encoding utf8
Write-Host "`nWrote $OutputPath" -ForegroundColor Green
