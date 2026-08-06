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

    STATUS: validated against PnP.PowerShell 3.3.0 and run read-only against a
    real tenant. The engine, schemas, CLI and test suite do not depend on this
    script: they run offline against fixtures.

.PARAMETER SiteUrl
    The site collection to inspect.

.PARAMETER OutputPath
    Where the evidence JSON is written.

.PARAMETER ClientId
    The application (client) id of an Entra ID app registration.

    Mandatory, and it is the thing that breaks a first run. Since
    PnP.PowerShell 2.99 the module ships with no multi-tenant application of
    its own, so a connection without a client id fails before it reaches the
    network: "Please specify a valid client id for an Entra ID App
    Registration". Verified against 3.3.0.

.PARAMETER DeviceLogin
    Authenticate with a device code instead of opening a browser. For hosts
    with no browser, and for automation that a person completes once.

.PARAMETER ListTitle
    Optional. Collect one list instead of the site.

.EXAMPLE
    ./Get-SpoEvidence.ps1 -SiteUrl https://contoso.sharepoint.com/sites/Finance `
        -ClientId 00000000-0000-0000-0000-000000000000 `
        -OutputPath ./evidence/finance-site.json

.NOTES
    Depends on PnP.PowerShell 3.x. Verified against 3.3.0, and what was
    verified is stated so that a later break is legible:

      Connect-PnPOnline            -Url, -Interactive, -DeviceLogin, -ClientId
      Get-PnPContext
      Get-PnPSiteCollectionAdmin   returns Microsoft.SharePoint.Client.User
                                   LoginName (String), PrincipalType (enum)
      Get-PnPList                  returns Microsoft.SharePoint.Client.List
                                   ItemCount (Int32),
                                   HasUniqueRoleAssignments (Boolean)

    HasUniqueRoleAssignments is not loaded by default and is requested through
    -Includes. ItemCount comes back without asking.

    IDENTITY. Both -Interactive and -DeviceLogin are delegated: the run sees
    what the signed-in person sees, and the evidence records that so no report
    built from it reads as a statement about the whole tenant. For a
    tenant-wide inventory the identity has to be an application with
    Sites.Read.All and admin consent, and that is a deliberate decision about
    access rather than a flag on this script. It is not implemented here.

    The token is not persisted between runs, so each run authenticates again.
    -PersistLogin exists on Connect-PnPOnline and is not used: a collector that
    leaves a reusable token on disk has widened the blast radius of the machine
    it runs on, and that is a decision for whoever operates it, not a default.

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

    [Parameter(Mandatory = $true)]
    [string] $ClientId,

    [Parameter()]
    [switch] $DeviceLogin,

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

if ($DeviceLogin) {
    Connect-PnPOnline -Url $SiteUrl -DeviceLogin -ClientId $ClientId
}
else {
    Connect-PnPOnline -Url $SiteUrl -Interactive -ClientId $ClientId
}

# Get-PnPWeb, not $context.Web. The context hands back a CSOM object whose
# properties are not loaded, so $context.Web.Title returns $null without
# raising anything, and the title went into the evidence as null. Found by
# running this against a real tenant; the schema rejected the null, which is
# what it is there for.
$web = Get-PnPWeb

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
        display_name = [string] $web.Title
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

# An optional field that could not be read is not written as null. The schema
# rejects null, and it is right to: "not known" has its own state on a fact,
# and on a descriptive field the absence of the key says the same thing
# without inventing a value.
foreach ($k in @('display_name', 'url')) {
    if ($resource.Contains($k) -and [string]::IsNullOrWhiteSpace($resource[$k])) {
        $resource.Remove($k)
    }
}

$evidence | ConvertTo-Json -Depth 12 | Set-Content -Path $OutputPath -Encoding utf8
Write-Host "Evidence written to $OutputPath"
