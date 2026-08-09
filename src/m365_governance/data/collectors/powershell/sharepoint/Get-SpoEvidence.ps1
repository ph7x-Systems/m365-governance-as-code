<#
.SYNOPSIS
    Collects SharePoint Online facts and emits normalised evidence JSON.

.DESCRIPTION
    The entry point. It orchestrates and does not collect: connect, select a
    slice, call one function from modules/, emit JSON. The engineering standard
    for every PowerShell file here is one document, and it is not this header:
    docs/POWERSHELL-STANDARDS.md.

    Read-only. Nothing under collectors/ has a write path: no Set-, New-,
    Remove-, Add-, Grant- or Revoke- cmdlet is called against a tenant, and CI
    proves it by parsing every file in the tree and failing on any mutating
    verb. Every file, because naming one path was true while there was one
    file and would have gone on passing while proving nothing about the rest.

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
      SiteSharing        the sharing configuration of one site. Needs -TenantUrl
                         as well as -SiteUrl: sharing settings are a tenant
                         property about a site, not a site property
      List               one list: item count and permission inheritance
      UniquePermissions  every list on a site, hidden ones included
      TenantSites        every site this identity can enumerate
      Modernity          how one site is built: template, branding, publishing
                         features, and how many of its pages are modern
      SpfxCatalog        what is in an app catalog. Cheap: one call
      SpfxPages          which components are on which pages. Expensive: it
                         opens every page, so it is opt-in and declares what
                         it managed to inspect
      Activity           when a person last changed something on a site, and
                         whether the site is in a state where nobody could
      Classification     the sensitivity label and classification on a site,
                         and whether they can be resolved to a name

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

.PARAMETER MaxPages
    SpfxPages only. Stop after this many pages. Reaching it produces partial
    coverage, stated in the evidence, and never a count presented as complete.

.PARAMETER ModifiedSince
    SpfxPages only. Skip pages the library says were last modified before this
    date. A page skipped this way is not a page without components: it is a
    page nobody looked at, and the coverage block says how many.

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
    [ValidateSet('SiteOwners', 'SiteSharing', 'TenantSharing', 'List', 'UniquePermissions', 'TenantSites', 'Modernity', 'SpfxCatalog', 'SpfxPages', 'Activity', 'Classification', 'Agents')]
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
    [int] $MaxItemsPerList = 20000,

    [Parameter()]
    [int] $MaxPages = 100,

    [Parameter()]
    [datetime] $ModifiedSince
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$CollectorVersion = '0.3.0'
$CollectorName = 'spo-collector'

# --- modules ----------------------------------------------------------------
#
# The engineering standard for every PowerShell file in this repository is one
# document: docs/POWERSHELL-STANDARDS.md. This file orchestrates and does not
# collect: connect, select a slice, call one function, emit JSON.
#
# Evidence first, because every other module imports it.

$Modules = Join-Path $PSScriptRoot 'modules'
foreach ($module in @('Evidence', 'Connection', 'Sites', 'Sharing', 'Permissions',
        'Modernity', 'Activity', 'Classification', 'Spfx', 'Agents')) {
    Import-Module (Join-Path $Modules "$module.psm1") -Force
}

# --- connect (read-only) -----------------------------------------------------

$TenantHost = Connect-Collector -Mode $Mode -ClientId $ClientId -SiteUrl $SiteUrl `
    -TenantUrl $TenantUrl -DeviceLogin:$DeviceLogin

Initialize-Evidence -CollectorName $CollectorName `
    -CollectorVersion $CollectorVersion -TenantHost $TenantHost


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
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts $result.facts -Requested @('owners') `
                -Completed $completed -Unavailable $unavailable)
    }

    'TenantSharing' {
        # One resource, not one per site. The tenant is what every site
        # inherits from when it sets nothing of its own.
        $tenant = Get-PnPTenant
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'tenant'
                    native_id = $TenantHost
                    tenant = (New-TenantIdentity)
                    scope = 'tenant'; parent = $null
                    display_name = $TenantUrl; url = $TenantUrl
                }) `
                -Facts (Get-TenantSharingFacts -Tenant $tenant) `
                -Requested @('tenant_sharing') -Completed @('tenant_sharing') `
                -Unavailable ([ordered]@{}) `
                -SourceApi 'PnP.PowerShell / SharePoint Admin')
    }

    'SiteSharing' {
        # Get-PnPTenantSite, not Get-PnPSite. SharingCapability is not a
        # property of the site: it is a tenant property about the site, and
        # -Includes on Get-PnPSite rejects it outright. Found by running this
        # against a real tenant, which is the only way it could have been
        # found: the name existed, the type existed, and the call failed at
        # the parameter set.
        #
        # The consequence is that this slice needs an administrative
        # connection. It is not a site-level read and pretending otherwise
        # would have produced a mode that only ever failed.
        $site = Get-PnPTenantSite -Identity $SiteUrl
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $site.Title; url = $SiteUrl
                }) `
                -Facts (Get-SharingFacts -Site $site) -Requested @('sharing') `
                -Completed @('sharing') -Unavailable ([ordered]@{}) `
                -SourceApi 'PnP.PowerShell / SharePoint Admin')
    }

    'List' {
        $list = Get-PnPList -Identity $ListTitle -Includes HasUniqueRoleAssignments, `
            IsSystemList, IsCatalog, IsApplicationList, BaseTemplate, Hidden
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'list'
                    native_id = "$SiteUrl::$ListTitle"
                    tenant = (New-TenantIdentity)
                    scope = 'container'; parent = [ordered]@{ workload = 'sharepoint'; type = 'site'; native_id = $SiteUrl }
                    display_name = $ListTitle; url = $SiteUrl
                }) `
                -Facts (Get-ListPermissionFacts -List $list `
                        -CountUniqueScopes:$CountUniqueScopes `
                        -MaxItemsPerList $MaxItemsPerList) `
                -Requested @('items', 'permissions') `
                -Completed @('items', 'permissions') -Unavailable ([ordered]@{}))
    }

    'UniquePermissions' {
        # Every list, including hidden ones. The filter that used to be here
        # was the collector deciding what mattered, and it decided wrong: a
        # hidden library is still a library, and three of the eight it did
        # return were catalogs anyway. Relevance is the profile's job, and it
        # separates rather than drops.
        $lists = @(Get-PnPList -Includes HasUniqueRoleAssignments, IsSystemList, `
                IsCatalog, IsApplicationList, BaseTemplate, Hidden)
        Write-Host "$($lists.Count) lists"
        foreach ($list in $lists) {
            $file = Join-Path $OutputPath ((Get-SafeName "$($TenantHost)-$($list.Title)") + '.json')
            Write-Evidence -Path $file -Evidence (New-Evidence `
                    -Resource ([ordered]@{
                        workload = 'sharepoint'; type = 'list'
                        native_id = "$SiteUrl::$($list.Title)"
                        tenant = (New-TenantIdentity)
                        scope = 'container'; parent = [ordered]@{ workload = 'sharepoint'; type = 'site'; native_id = $SiteUrl }
                        display_name = [string] $list.Title; url = $SiteUrl
                    }) `
                    -Facts (Get-ListPermissionFacts -List $list `
                        -CountUniqueScopes:$CountUniqueScopes `
                        -MaxItemsPerList $MaxItemsPerList) `
                    -Requested @('items', 'permissions') `
                    -Completed @('items', 'permissions') -Unavailable ([ordered]@{}))
        }
    }

    'Modernity' {
        $web = Get-PnPWeb -Includes WebTemplate, Configuration, MasterUrl, `
            CustomMasterUrl, AlternateCssUrl
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-ModernityFacts -Web $web) `
                -Requested @('web', 'pages') -Completed @('web', 'pages') `
                -Unavailable ([ordered]@{}))
    }

    'Classification' {
        $web = Get-PnPWeb
        $site = Get-PnPSite -Includes SensitivityLabelId, SensitivityLabelInfo, Classification, GroupId
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-ClassificationFacts -Site $site) `
                -Requested @('classification') -Completed @('classification') `
                -Unavailable ([ordered]@{}))
    }

    'Activity' {
        $web = Get-PnPWeb -Includes LastItemModifiedDate, LastItemUserModifiedDate, Created
        $tenantSite = $null
        $tenantSiteError = 'It was not requested: -TenantUrl was not given.'
        if ($TenantUrl) {
            try { $tenantSite = Get-PnPTenantSite -Identity $SiteUrl }
            catch {
                $tenantSite = $null
                $tenantSiteError = $_.Exception.Message
            }
        }
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-ActivityFacts -Web $web -TenantSite $tenantSite `
                        -TenantSiteError $tenantSiteError) `
                -Requested @('activity') -Completed @('activity') `
                -Unavailable ([ordered]@{}))
    }

    'Agents' {
        # Agents are files in the Site Assets library, so this is a site read
        # and not an admin centre one. Whatever this identity cannot open does
        # not appear, which is why coverage says `partial` rather than letting
        # the count pass for a complete one.
        $web = Get-PnPWeb
        $facts = Get-AgentFacts
        $nota = New-Unavailable -State 'partial' -Detail (
            'Agents are files, so this is what the running identity can see ' +
            'in this site collection. A site with no agents and a site this ' +
            'identity cannot open return the same empty result.')
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts $facts -Requested @('agents', 'enumeration') `
                -Completed @('agents') `
                -Unavailable ([ordered]@{ enumeration = $nota }))
    }

    'SpfxCatalog' {
        $scope = if ($TenantUrl) { 'Tenant' } else { 'Site' }
        $web = Get-PnPWeb
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-SpfxCatalogFacts -Scope $scope) `
                -Requested @('spfx') -Completed @('spfx') -Unavailable ([ordered]@{}))
    }

    'SpfxPages' {
        $web = Get-PnPWeb
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    workload = 'sharepoint'; type = 'site'
                    native_id = $SiteUrl
                    tenant = (New-TenantIdentity)
                    scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-SpfxPageFacts -MaxPages $MaxPages `
                        -ModifiedSince $ModifiedSince) `
                -Requested @('spfx', 'pages') -Completed @('spfx', 'pages') `
                -Unavailable ([ordered]@{}))
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
                        workload = 'sharepoint'; type = 'site'
                        native_id = [string] $tenantSite.Url
                        tenant = (New-TenantIdentity)
                        scope = 'collection'; parent = [ordered]@{ workload = 'sharepoint'; type = 'tenant'; native_id = $TenantHost }
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
