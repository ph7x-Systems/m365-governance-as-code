<#
    validate-sandbox.ps1

    The four validations that were written against documentation and never
    observed, in the order the owner set, in one run.

    You authenticate. Everything after that is automatic.

        pwsh tools/validate-sandbox.ps1 -TenantUrl https://y75hx-admin.sharepoint.com `
                                        -SiteUrl   https://y75hx.sharepoint.com `
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
Say "---"
Say ""
Say "**Nothing is concluded here.** Whether any of this becomes a rule is decided against Microsoft's documentation, in the open, and a cmdlet is not a reason."

$dir = Split-Path -Parent $OutputPath
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
$report -join "`n" | Set-Content -Path $OutputPath -Encoding utf8
Write-Host "`nWrote $OutputPath" -ForegroundColor Green
