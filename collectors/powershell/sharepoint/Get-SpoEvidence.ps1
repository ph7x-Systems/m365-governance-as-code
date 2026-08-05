<#
.SYNOPSIS
    Collects SharePoint facts and emits normalised evidence JSON.

.DESCRIPTION
    Read-only. This script has no write path: it calls no Set-, New-, Remove-
    or Add- cmdlet, and it never changes anything in a tenant.

    It returns what it observed. It never returns is_compliant, risk, score or
    a recommended action, because a collector that judges has made the rule
    unreviewable: the judgement moves out of a reviewable diff and into code.

    Every fact carries a collection state. A fact it could not read says so,
    with a reason. It never returns an empty list in place of an error, and it
    never presents a truncated response as a complete one.

    STATUS: written against the documented PnP.PowerShell surface and NOT yet
    run against a tenant. The cmdlets it depends on are listed under
    .NOTES so that a first run can be verified deliberately rather than
    discovered. The engine, schemas, CLI and test suite do not depend on this
    script: they run offline against fixtures.

.PARAMETER SiteUrl
    The site collection to inspect.

.PARAMETER OutputPath
    Where the evidence JSON is written.

.PARAMETER ListTitle
    Optional. Collect one list instead of the site.

.EXAMPLE
    ./Get-SpoEvidence.ps1 -SiteUrl https://contoso.sharepoint.com/sites/Finance `
        -OutputPath ./evidence/finance-site.json

.NOTES
    Depends on PnP.PowerShell:
      Connect-PnPOnline
      Get-PnPSiteCollectionAdmin   (site owners)
      Get-PnPList                  (ItemCount, HasUniqueRoleAssignments)

    Group expansion is NOT attempted in this version. A group owner is one
    principal and may be forty people, so the script emits expansion_complete
    = false and a minimum_count rather than a count it cannot prove. The
    engine reasons from that bound and still decides where the bound settles
    the question.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $SiteUrl,

    [Parameter(Mandatory = $true)]
    [string] $OutputPath,

    [Parameter()]
    [string] $ListTitle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CollectorVersion = '0.1.0'

function New-Unavailable {
    param([string] $State, [string] $Detail)
    return [ordered]@{ state = $State; detail = $Detail }
}

function New-ScalarFact {
    param($Value, [string] $RawField)
    return [ordered]@{
        state = 'observed'
        value = $Value
        raw   = [ordered]@{ field = $RawField; value = $Value }
    }
}

function Resolve-FailureState {
    <#
        Maps an exception onto a collection state. permission-denied is kept
        separate from missing because it is the only one whose fix is a human
        decision about access, and the one most often laundered into
        "no data, therefore fine".
    #>
    param([System.Management.Automation.ErrorRecord] $ErrorRecord)

    $message = $ErrorRecord.Exception.Message
    if ($message -match 'Access denied|Unauthorized|403|does not have permission') {
        return 'permission-denied'
    }
    if ($message -match 'not found|404|does not exist') {
        return 'missing'
    }
    if ($message -match 'not supported|NotImplemented') {
        return 'not-supported'
    }
    return 'missing'
}

function Get-SiteOwnerFacts {
    $requested = 'owners'
    try {
        $admins = @(Get-PnPSiteCollectionAdmin -ErrorAction Stop)
    }
    catch {
        return @{
            facts       = $null
            unavailable = New-Unavailable -State (Resolve-FailureState $_) -Detail $_.Exception.Message
            block       = $requested
        }
    }

    $direct = @()
    $groups = @()
    foreach ($admin in $admins) {
        $isGroup = $admin.PrincipalType -ne 'User'
        if ($isGroup) {
            $groups += [ordered]@{
                principal_id   = [string] $admin.LoginName
                principal_type = 'group'
                # Not attempted, and said so. A status of complete here would
                # be a count this script cannot prove.
                expansion      = [ordered]@{ status = 'not-attempted' }
            }
        }
        else {
            $direct += [ordered]@{
                principal_id   = [string] $admin.LoginName
                principal_type = 'user'
            }
        }
    }

    $owners = [ordered]@{ state = 'observed'; direct = $direct; groups = $groups }
    if ($groups.Count -eq 0) {
        $owners['expansion_complete'] = $true
        $owners['effective_count'] = $direct.Count
    }
    else {
        $owners['expansion_complete'] = $false
        $owners['minimum_count'] = $direct.Count
    }

    return @{ facts = @{ owners = $owners }; unavailable = $null; block = $requested }
}

function Get-ListFacts {
    param([string] $Title)

    try {
        $list = Get-PnPList -Identity $Title -Includes HasUniqueRoleAssignments -ErrorAction Stop
    }
    catch {
        return @{
            facts       = $null
            unavailable = New-Unavailable -State (Resolve-FailureState $_) -Detail $_.Exception.Message
            block       = 'items'
        }
    }

    return @{
        facts = @{
            items       = @{ count = New-ScalarFact -Value ([int] $list.ItemCount) -RawField 'ItemCount' }
            permissions = @{
                inheritance_broken = New-ScalarFact `
                    -Value ([bool] $list.HasUniqueRoleAssignments) `
                    -RawField 'hasUniqueRoleAssignments'
            }
        }
        unavailable = $null
        block       = 'items'
    }
}

# --- connect (read-only) -----------------------------------------------------

Connect-PnPOnline -Url $SiteUrl -Interactive
$context = Get-PnPContext

$requested = @()
$completed = @()
$unavailable = [ordered]@{}
$facts = [ordered]@{}

if ($ListTitle) {
    $requested = @('items', 'permissions')
    $result = Get-ListFacts -Title $ListTitle
    if ($null -eq $result.facts) {
        $unavailable[$result.block] = $result.unavailable
    }
    else {
        foreach ($key in $result.facts.Keys) { $facts[$key] = $result.facts[$key] }
        $completed = @('items', 'permissions')
    }
    $resource = [ordered]@{
        id           = "$SiteUrl::$ListTitle"
        type         = 'list'
        display_name = $ListTitle
        url          = $SiteUrl
    }
}
else {
    $requested = @('owners')
    $result = Get-SiteOwnerFacts
    if ($null -eq $result.facts) {
        $unavailable[$result.block] = $result.unavailable
    }
    else {
        foreach ($key in $result.facts.Keys) { $facts[$key] = $result.facts[$key] }
        $completed = @('owners')
    }
    $resource = [ordered]@{
        id           = $SiteUrl
        type         = 'site'
        display_name = $context.Web.Title
        url          = $SiteUrl
    }
}

$evidence = [ordered]@{
    schema_version = '1.0'
    provenance     = [ordered]@{
        collected_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        collector         = 'spo-collector'
        collector_version = $CollectorVersion
        source_system     = 'SharePoint Online'
        source_api        = 'PnP.PowerShell / CSOM'
        tenant_id         = ([uri] $SiteUrl).Host
        # Interactive sign-in sees what one person sees. Recording this is the
        # difference between a partial audit and a misleading one.
        identity_kind     = 'delegated'
        scopes            = @('AllSites.Read')
    }
    coverage       = [ordered]@{
        requested   = $requested
        completed   = $completed
        unavailable = $unavailable
    }
    resource       = $resource
    facts          = $facts
}

$evidence | ConvertTo-Json -Depth 12 | Set-Content -Path $OutputPath -Encoding utf8
Write-Host "Evidence written to $OutputPath"
