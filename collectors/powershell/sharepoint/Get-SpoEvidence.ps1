<#
.SYNOPSIS
    Collects SharePoint Online facts and emits normalised evidence JSON.

.DESCRIPTION
    Read-only. This script has no write path: it calls no Set-, New-, Remove-,
    Add-, Grant- or Revoke- cmdlet against a tenant, and CI proves it by
    parsing this file and failing on any mutating verb.

    It returns what it observed. It never returns is_compliant, risk, score or
    a recommended action, because a collector that judges has made the rule
    unreviewable: the judgement moves out of a reviewable diff and into code.

    Every fact carries a collection state. A fact it could not read says so,
    with a reason. It never returns an empty list in place of an error, and it
    never presents a truncated response as a complete one.

    Validated against PnP.PowerShell 3.3.0 and run read-only against a live
    tenant. The engine, schemas, CLI and test suite do not depend on this
    script: they run offline against fixtures.

.PARAMETER Mode
    What to collect. One evidence document is written per resource, so a mode
    that reads many resources writes many files into -OutputPath.

      SiteOwners         the owners of one site
      SiteSharing        the sharing configuration of one site
      List               one list: item count and permission inheritance
      UniquePermissions  every visible list on a site
      TenantSites        every site this identity can enumerate

.PARAMETER SiteUrl
    The site to inspect. Required by every mode except TenantSites.

.PARAMETER TenantUrl
    The admin centre, https://<tenant>-admin.sharepoint.com. TenantSites only.

.PARAMETER OutputPath
    A file for the single-resource modes, a directory for the rest.

.PARAMETER ClientId
    The application (client) id of an Entra ID app registration.

    Mandatory, and it is the thing that breaks a first run. Since
    PnP.PowerShell 2.99 the module ships with no multi-tenant application of
    its own, so a connection without a client id fails before it reaches the
    network: "Please specify a valid client id for an Entra ID App
    Registration". Verified against 3.3.0.

.PARAMETER DeviceLogin
    Authenticate with a device code instead of opening a browser.

.PARAMETER CountUniqueScopes
    UniquePermissions only. Walk the items of each list to count unique
    permission scopes.

    Off by default because it is the expensive part: it reads every item of
    every list. With it off the count is reported as `not-supported`, which is
    the truth about this run rather than a zero, and a rule that needs the
    number returns `unknown`.

.PARAMETER MaxItemsPerList
    The cap on that walk. Reaching it produces `partial` and a lower bound,
    never a number presented as complete.

.EXAMPLE
    ./Get-SpoEvidence.ps1 -Mode TenantSites `
        -TenantUrl https://contoso-admin.sharepoint.com `
        -ClientId 00000000-0000-0000-0000-000000000000 `
        -OutputPath ./evidence/sites/

.EXAMPLE
    ./Get-SpoEvidence.ps1 -Mode UniquePermissions `
        -SiteUrl https://contoso.sharepoint.com/sites/Finance `
        -ClientId 00000000-0000-0000-0000-000000000000 `
        -CountUniqueScopes -OutputPath ./evidence/lists/

.NOTES
    Depends on PnP.PowerShell 3.x. Verified against 3.3.0:

      Connect-PnPOnline           -Url, -Interactive, -DeviceLogin, -ClientId
      Get-PnPWeb, Get-PnPSite, Get-PnPTenantSite
      Get-PnPSiteCollectionAdmin  Microsoft.SharePoint.Client.User
                                  LoginName (String), PrincipalType (enum)
      Get-PnPList                 Microsoft.SharePoint.Client.List
                                  ItemCount (Int32),
                                  HasUniqueRoleAssignments (Boolean)
      Get-PnPListItem             for the scope walk, paged

    HasUniqueRoleAssignments is not loaded by default and is requested through
    -Includes. ItemCount comes back without asking.

    IDENTITY. Both -Interactive and -DeviceLogin are delegated: the run sees
    what the signed-in person sees, and the evidence records that so no report
    built from it reads as a statement about the whole tenant. TenantSites
    enumerates what the identity can enumerate, which for a delegated run is
    not the tenant, and every document it writes says so in its coverage.

    The token is not persisted between runs. -PersistLogin exists and is not
    used: a collector that leaves a reusable token on disk has widened the
    blast radius of the machine it runs on, and that is a decision for whoever
    operates it, not a default.

    Group expansion is NOT attempted. A group owner is one principal and may
    be forty people, so the script emits expansion_complete = false and a
    minimum_count rather than a count it cannot prove.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('SiteOwners', 'SiteSharing', 'List', 'UniquePermissions', 'TenantSites')]
    [string] $Mode,

    [Parameter(Mandatory = $true)]
    [string] $OutputPath,

    [Parameter(Mandatory = $true)]
    [string] $ClientId,

    [Parameter()]
    [string] $SiteUrl,

    [Parameter()]
    [string] $TenantUrl,

    [Parameter()]
    [string] $ListTitle,

    [Parameter()]
    [switch] $DeviceLogin,

    [Parameter()]
    [switch] $CountUniqueScopes,

    [Parameter()]
    [int] $MaxItemsPerList = 20000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CollectorVersion = '0.3.0'
$CollectorName = 'spo-collector'

# --- shapes -----------------------------------------------------------------

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

function New-AbsentFact {
    param([string] $State, [string] $Detail)
    return [ordered]@{ state = $State; detail = $Detail }
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
    if ($message -match 'not found|404|does not exist') { return 'missing' }
    if ($message -match 'not supported|NotImplemented') { return 'not-supported' }
    return 'missing'
}

function New-Evidence {
    param(
        $Resource,
        $Facts,
        [string[]] $Requested,
        [string[]] $Completed,
        $Unavailable,
        [string] $SourceApi = 'PnP.PowerShell / CSOM'
    )
    return [ordered]@{
        schema_version = '1.0'
        provenance     = [ordered]@{
            collected_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            collector         = $CollectorName
            collector_version = $CollectorVersion
            source_system     = 'SharePoint Online'
            source_api        = $SourceApi
            tenant_id         = $script:TenantHost
            # Interactive and device sign-in are both delegated. Recording it
            # is the difference between a partial audit and a misleading one.
            identity_kind     = 'delegated'
            scopes            = @('AllSites.Read')
        }
        coverage       = [ordered]@{
            requested   = $Requested
            completed   = $Completed
            unavailable = $Unavailable
        }
        resource       = $Resource
        facts          = $Facts
    }
}

function Write-Evidence {
    param($Evidence, [string] $Path)

    # An optional field that could not be read is not written as null. The
    # schema rejects null, and it is right to: "not known" has its own state on
    # a fact, and on a descriptive field the absence of the key says the same
    # thing without inventing a value.
    foreach ($k in @('display_name', 'url')) {
        if ($Evidence.resource.Contains($k) -and
            [string]::IsNullOrWhiteSpace($Evidence.resource[$k])) {
            $Evidence.resource.Remove($k)
        }
    }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    $Evidence | ConvertTo-Json -Depth 14 | Set-Content -Path $Path -Encoding utf8
    Write-Host "  $Path"
}

function Get-SafeName {
    param([string] $Value)
    return ($Value -replace '^https?://', '' -replace '[^A-Za-z0-9._-]', '-').Trim('-')
}

# --- facts ------------------------------------------------------------------

function Get-OwnerFacts {
    try {
        $admins = @(Get-PnPSiteCollectionAdmin -ErrorAction Stop)
    }
    catch {
        $state = Resolve-FailureState $_
        return @{
            facts       = @{ owners = New-AbsentFact -State $state -Detail $_.Exception.Message }
            unavailable = New-Unavailable -State $state -Detail $_.Exception.Message
        }
    }

    $direct = @(); $groups = @()
    foreach ($admin in $admins) {
        if ($admin.PrincipalType -ne 'User') {
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
    # Counted separately from the total because they answer different
    # questions. The total asks how many administrators there are; this asks
    # whether any of them is a person somebody could ring.
    $owners['direct_count'] = New-ScalarFact -Value $direct.Count -RawField 'PrincipalType'
    $owners['group_count'] = New-ScalarFact -Value $groups.Count -RawField 'PrincipalType'
    if ($groups.Count -eq 0) {
        $owners['expansion_complete'] = $true
        $owners['effective_count'] = $direct.Count
    }
    else {
        $owners['expansion_complete'] = $false
        $owners['minimum_count'] = $direct.Count
    }
    return @{ facts = @{ owners = $owners }; unavailable = $null }
}

function Get-ListPermissionFacts {
    param($List)

    $facts = [ordered]@{
        items       = [ordered]@{
            count = New-ScalarFact -Value ([int] $List.ItemCount) -RawField 'ItemCount'
        }
        permissions = [ordered]@{
            inheritance_broken = New-ScalarFact `
                -Value ([bool] $List.HasUniqueRoleAssignments) `
                -RawField 'hasUniqueRoleAssignments'
        }
    }

    if (-not $CountUniqueScopes) {
        # Not a zero. This run did not look, and saying so is the only honest
        # option: a rule that needs the number returns unknown, which is
        # correct, rather than passing on a count nobody produced.
        $facts.permissions['unique_scope_count'] = New-AbsentFact `
            -State 'not-supported' `
            -Detail 'Not counted. Re-run with -CountUniqueScopes to walk the items.'
        return $facts
    }

    try {
        $seen = 0; $unique = 0; $capped = $false
        $items = Get-PnPListItem -List $List -PageSize 500 `
            -Fields 'ID', 'HasUniqueRoleAssignments' -ErrorAction Stop
        foreach ($item in $items) {
            if ($seen -ge $MaxItemsPerList) { $capped = $true; break }
            $seen++
            if ($item['HasUniqueRoleAssignments']) { $unique++ }
        }
        # The list itself is a scope when its own inheritance is broken.
        if ($List.HasUniqueRoleAssignments) { $unique++ }

        if ($capped) {
            $facts.permissions['unique_scope_count'] = [ordered]@{
                state  = 'partial'
                value  = $unique
                detail = "Stopped at $MaxItemsPerList items. The real count is at least this."
                raw    = [ordered]@{ field = 'HasUniqueRoleAssignments'; value = $unique }
            }
        }
        else {
            $facts.permissions['unique_scope_count'] =
            New-ScalarFact -Value $unique -RawField 'HasUniqueRoleAssignments'
        }
    }
    catch {
        $facts.permissions['unique_scope_count'] =
        New-AbsentFact -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }
    return $facts
}

function Get-SharingFacts {
    param($Site)

    # SharePoint enforces that a site cannot be more permissive than the
    # tenant, so both values are reported for context rather than for a rule
    # about one exceeding the other: that rule could never fire.
    $facts = [ordered]@{ sharing = [ordered]@{} }
    $map = [ordered]@{
        capability                 = 'SharingCapability'
        default_link_type          = 'DefaultSharingLinkType'
        default_link_permission    = 'DefaultLinkPermission'
        anonymous_link_expiry_days = 'AnonymousLinkExpirationInDays'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $Site.$property
            if ($null -eq $value -or "$value" -eq '') {
                $facts.sharing[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this site."
            }
            elseif ($name -eq 'anonymous_link_expiry_days') {
                $facts.sharing[$name] =
                New-ScalarFact -Value ([int] $value) -RawField $property
            }
            else {
                $facts.sharing[$name] =
                New-ScalarFact -Value ("$value") -RawField $property
            }
        }
        catch {
            $facts.sharing[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }
    return $facts
}

function Get-SiteInventoryFacts {
    param($TenantSite)

    $facts = [ordered]@{ site = [ordered]@{} }
    $map = [ordered]@{
        template              = 'Template'
        lock_state            = 'LockState'
        storage_used_mb       = 'StorageUsageCurrent'
        storage_quota_mb      = 'StorageQuota'
        last_content_modified = 'LastContentModifiedDate'
        hub_site_id           = 'HubSiteId'
        sharing_capability    = 'SharingCapability'
        group_id              = 'GroupId'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $TenantSite.$property
            if ($null -eq $value -or "$value" -eq '') {
                $facts.site[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this site."
            }
            elseif ($name -in @('storage_used_mb', 'storage_quota_mb')) {
                $facts.site[$name] = New-ScalarFact -Value ([int] $value) -RawField $property
            }
            else {
                $facts.site[$name] = New-ScalarFact -Value ("$value") -RawField $property
            }
        }
        catch {
            $facts.site[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # Derived from the two figures beside it, and only when both were read. A
    # percentage of a quota nobody returned would be a number with no
    # denominator, which is worse than not having it.
    $used = $facts.site['storage_used_mb']
    $quota = $facts.site['storage_quota_mb']
    if ($used.state -eq 'observed' -and $quota.state -eq 'observed' -and
        [double] $quota.value -gt 0) {
        $percent = [int] [math]::Round(([double] $used.value / [double] $quota.value) * 100)
        $facts.site['storage_used_percent'] =
        New-ScalarFact -Value $percent -RawField 'StorageUsageCurrent/StorageQuota'
    }
    else {
        $facts.site['storage_used_percent'] = New-AbsentFact -State 'missing' `
            -Detail 'Derived from used and quota, and one of them was not read.'
    }

    # Derived, and derived from something observed: an empty GroupId is how a
    # site says it is not group-connected.
    $group = $facts.site['group_id']
    if ($group.state -eq 'observed') {
        $connected = ($group.value -ne '00000000-0000-0000-0000-000000000000')
        $facts.site['group_connected'] = New-ScalarFact -Value $connected -RawField 'GroupId'
    }
    else {
        $facts.site['group_connected'] = New-AbsentFact -State $group.state `
            -Detail 'Derived from GroupId, which was not read.'
    }
    return $facts
}

# --- connect (read-only) -----------------------------------------------------

$connectUrl = if ($Mode -eq 'TenantSites') { $TenantUrl } else { $SiteUrl }
if (-not $connectUrl) {
    $needed = if ($Mode -eq 'TenantSites') { '-TenantUrl' } else { '-SiteUrl' }
    throw "Mode $Mode needs $needed."
}

if ($DeviceLogin) {
    Connect-PnPOnline -Url $connectUrl -DeviceLogin -ClientId $ClientId
}
else {
    Connect-PnPOnline -Url $connectUrl -Interactive -ClientId $ClientId
}

$script:TenantHost = ([uri] $connectUrl).Host

# --- collect -----------------------------------------------------------------

switch ($Mode) {

    'SiteOwners' {
        # Get-PnPWeb, not $context.Web. The context hands back a CSOM object
        # whose properties are not loaded, so reading .Title through it returns
        # $null without raising anything. Found by running against a real
        # tenant; the schema rejected the null, which is what it is there for.
        $web = Get-PnPWeb
        $result = Get-OwnerFacts
        $unavailable = [ordered]@{}
        $completed = @('owners')
        if ($null -ne $result.unavailable) {
            $unavailable['owners'] = $result.unavailable
            $completed = @()
        }
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    id = $SiteUrl; type = 'site'
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts $result.facts -Requested @('owners') `
                -Completed $completed -Unavailable $unavailable)
    }

    'SiteSharing' {
        $web = Get-PnPWeb
        $site = Get-PnPSite -Includes SharingCapability, DefaultSharingLinkType, `
            DefaultLinkPermission, AnonymousLinkExpirationInDays
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    id = $SiteUrl; type = 'site'
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-SharingFacts -Site $site) -Requested @('sharing') `
                -Completed @('sharing') -Unavailable ([ordered]@{}))
    }

    'List' {
        $list = Get-PnPList -Identity $ListTitle -Includes HasUniqueRoleAssignments
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    id = "$SiteUrl::$ListTitle"; type = 'list'
                    display_name = $ListTitle; url = $SiteUrl
                }) `
                -Facts (Get-ListPermissionFacts -List $list) `
                -Requested @('items', 'permissions') `
                -Completed @('items', 'permissions') -Unavailable ([ordered]@{}))
    }

    'UniquePermissions' {
        $lists = @(Get-PnPList -Includes HasUniqueRoleAssignments |
                Where-Object { -not $_.Hidden })
        Write-Host "$($lists.Count) lists"
        foreach ($list in $lists) {
            $file = Join-Path $OutputPath ((Get-SafeName "$($script:TenantHost)-$($list.Title)") + '.json')
            Write-Evidence -Path $file -Evidence (New-Evidence `
                    -Resource ([ordered]@{
                        id = "$SiteUrl::$($list.Title)"; type = 'list'
                        display_name = [string] $list.Title; url = $SiteUrl
                    }) `
                    -Facts (Get-ListPermissionFacts -List $list) `
                    -Requested @('items', 'permissions') `
                    -Completed @('items', 'permissions') -Unavailable ([ordered]@{}))
        }
    }

    'TenantSites' {
        # What this identity can enumerate. For a delegated run that is not the
        # tenant, and every document says so in its coverage rather than
        # letting a report imply completeness.
        $sites = @(Get-PnPTenantSite)
        Write-Host "$($sites.Count) sites enumerated by this identity"
        $note = New-Unavailable -State 'partial' -Detail (
            "Enumerated $($sites.Count) sites with a delegated identity. Sites " +
            'this identity cannot see are absent from this run, and their ' +
            'number is not knowable from here.')
        foreach ($tenantSite in $sites) {
            $file = Join-Path $OutputPath ((Get-SafeName $tenantSite.Url) + '.json')
            Write-Evidence -Path $file -Evidence (New-Evidence `
                    -Resource ([ordered]@{
                        id = [string] $tenantSite.Url; type = 'site'
                        display_name = [string] $tenantSite.Title
                        url = [string] $tenantSite.Url
                    }) `
                    -Facts (Get-SiteInventoryFacts -TenantSite $tenantSite) `
                    -Requested @('site', 'enumeration') -Completed @('site') `
                    -Unavailable ([ordered]@{ enumeration = $note }) `
                    -SourceApi 'PnP.PowerShell / SharePoint Admin')
        }
    }
}

Write-Host 'Done.'
