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
    [ValidateSet('SiteOwners', 'SiteSharing', 'List', 'UniquePermissions', 'TenantSites', 'Modernity', 'SpfxCatalog', 'SpfxPages')]
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
        # What kind of list SharePoint says this is. Collected, not judged:
        # the engine turns these into a class, and the order of precedence it
        # uses lives in one reviewable function rather than here.
        #
        # Nothing is filtered on them. A collector that dropped system lists
        # would be deciding what matters, and a library holding 60,000 unique
        # scopes matters whoever created it.
        list        = [ordered]@{
            is_catalog     = New-ScalarFact -Value ([bool] $List.IsCatalog) -RawField 'IsCatalog'
            is_system      = New-ScalarFact -Value ([bool] $List.IsSystemList) -RawField 'IsSystemList'
            is_application = New-ScalarFact -Value ([bool] $List.IsApplicationList) -RawField 'IsApplicationList'
            hidden         = New-ScalarFact -Value ([bool] $List.Hidden) -RawField 'Hidden'
            base_template  = New-ScalarFact -Value ([int] $List.BaseTemplate) -RawField 'BaseTemplate'
        }
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

    # `None` is not a link type. It is how a site says it sets no default of
    # its own and follows the tenant, and the tenant setting is not in this
    # document. Reported as observed, a rule comparing it against
    # AnonymousAccess would return `pass` while knowing nothing: the tenant
    # default it inherits could be exactly that.
    #
    # So the effective default is a separate fact, and it is missing when the
    # site inherits. The rule then answers `unknown`, which is the truth.
    $declared = $facts.sharing['default_link_type']
    if ($declared.state -eq 'observed' -and $declared.value -ne 'None') {
        $facts.sharing['effective_default_link_type'] =
        New-ScalarFact -Value $declared.value -RawField 'DefaultSharingLinkType'
    }
    elseif ($declared.state -eq 'observed') {
        $facts.sharing['effective_default_link_type'] = New-AbsentFact -State 'missing' `
            -Detail ('The site sets no default of its own and follows the tenant. ' +
                     'The tenant setting was not read by this collection.')
    }
    else {
        $facts.sharing['effective_default_link_type'] = New-AbsentFact `
            -State $declared.state -Detail 'Derived from the site setting, which was not read.'
    }
    return $facts
}

function Get-SpfxCatalogFacts {
    param([string] $Scope)

    try {
        $apps = @(Get-PnPApp -Scope $Scope -ErrorAction Stop)
    }
    catch {
        return [ordered]@{
            spfx = [ordered]@{
                solutions = New-AbsentFact -State (Resolve-FailureState $_) `
                    -Detail $_.Exception.Message
                solution_count = New-AbsentFact -State (Resolve-FailureState $_) `
                    -Detail 'The catalog was not read.'
            }
        }
    }

    # Seven properties, and seven is all AppMetadata has. Notably absent:
    # anything saying a solution is deployed tenant-wide. That flag lives in
    # the Tenant Wide Extensions list, not on the app, so this collector does
    # not report it and no rule may assume it.
    $solutions = @()
    foreach ($app in $apps) {
        $solutions += [ordered]@{
            id                = [string] $app.Id
            title             = [string] $app.Title
            catalog_version   = [string] $app.AppCatalogVersion
            installed_version = [string] $app.InstalledVersion
            deployed          = [bool] $app.Deployed
            can_upgrade       = [bool] $app.CanUpgrade
            client_side       = [bool] $app.IsClientSideSolution
        }
    }
    # Derived from two version numbers the catalog reports side by side. Not
    # from CanUpgrade alone: that flag and the version pair should agree, and
    # a rule reading the pair can be checked by a reader against the numbers
    # printed beside it.
    $behind = @($solutions | Where-Object {
            $_.catalog_version -and $_.installed_version -and
            $_.catalog_version -ne $_.installed_version
        })

    return [ordered]@{
        spfx = [ordered]@{
            catalog_scope    = New-ScalarFact -Value $Scope -RawField 'Get-PnPApp -Scope'
            solutions        = New-ScalarFact -Value $solutions -RawField 'AppMetadata'
            solution_count   = New-ScalarFact -Value $solutions.Count -RawField 'AppMetadata'
            upgradable_count = New-ScalarFact -Value $behind.Count `
                -RawField 'AppCatalogVersion vs InstalledVersion'
        }
    }
}

function Get-SpfxPageFacts {
    $facts = [ordered]@{ spfx = [ordered]@{}; pages = [ordered]@{} }

    try {
        $all = @(Get-PnPPage -ErrorAction Stop)
    }
    catch {
        $state = Resolve-FailureState $_
        $facts.pages['total'] = New-AbsentFact -State $state -Detail $_.Exception.Message
        $facts.pages['inspected'] = New-AbsentFact -State $state -Detail 'No page was opened.'
        $facts.spfx['components'] = New-AbsentFact -State $state -Detail 'No page was opened.'
        return $facts
    }

    $facts.pages['total'] = New-ScalarFact -Value $all.Count -RawField 'Get-PnPPage'

    $components = @()
    $inspected = 0
    $failed = @()
    $skippedByDate = 0

    foreach ($page in $all) {
        if ($inspected -ge $MaxPages) { break }
        if ($PSBoundParameters.ContainsKey('ModifiedSince')) {
            $when = $null
            try { $when = $page.PageListItem['Modified'] } catch { $when = $null }
            if ($null -ne $when -and [datetime] $when -lt $ModifiedSince) {
                $skippedByDate++
                continue
            }
        }
        try {
            $found = @(Get-PnPPageComponent -Page $page.Name -ErrorAction Stop)
            $inspected++
            foreach ($c in $found) {
                $components += [ordered]@{
                    page        = [string] $page.Name
                    instance_id = [string] $c.InstanceId
                    web_part_id = [string] $c.WebPartId
                    title       = [string] $c.Title
                }
            }
        }
        catch {
            $failed += [ordered]@{ page = [string] $page.Name; detail = $_.Exception.Message }
        }
    }

    $facts.pages['inspected'] = New-ScalarFact -Value $inspected -RawField 'Get-PnPPageComponent'
    if ($failed.Count -gt 0) {
        $facts.pages['not_inspected'] = [ordered]@{
            state  = 'partial'
            value  = $failed.Count
            detail = "$($failed.Count) pages could not be opened. A page nobody read is not a page without components."
            raw    = [ordered]@{ field = 'Get-PnPPageComponent'; value = $failed.Count }
        }
    }
    if ($skippedByDate -gt 0) {
        $facts.pages['skipped_by_date'] =
        New-ScalarFact -Value $skippedByDate -RawField 'ModifiedSince'
    }

    # The counts have to add up, and once they did not: a run reported 9 pages
    # total, 8 inspected and 7 that could not be opened. Fifteen outcomes for
    # nine pages. Every one of those numbers was believable on its own, and a
    # report built on them would have been believable too.
    #
    # A collector that cannot reconcile its own counting says so, in the
    # evidence, and the facts that depend on it become invalid rather than
    # merely surprising. `invalid` is the right state: the fix is in this
    # script, not in another collection.
    $accounted = $inspected + $failed.Count + $skippedByDate
    $remaining = $all.Count - $accounted
    if ($remaining -lt 0 -or ($remaining -gt 0 -and $inspected -ge $MaxPages -eq $false)) {
        $note = ("Counted $inspected inspected, $($failed.Count) unreadable and " +
                 "$skippedByDate skipped, which is $accounted outcomes for " +
                 "$($all.Count) pages. These cannot all be true.")
        foreach ($key in @('inspected', 'not_inspected')) {
            if ($facts.pages.Contains($key)) {
                $facts.pages[$key] = [ordered]@{ state = 'invalid'; detail = $note }
            }
        }
        $facts.spfx['reconciled'] = [ordered]@{ state = 'invalid'; detail = $note }
        return $facts
    }
    $facts.spfx['reconciled'] = New-ScalarFact -Value $true -RawField 'inspected + unreadable + skipped'
    if ($remaining -gt 0) {
        $facts.pages['not_reached'] = New-ScalarFact -Value $remaining `
            -RawField "MaxPages ($MaxPages)"
    }

    # Complete only when every page was opened. Anything else is partial, and
    # partial is a lower bound: more pages can only add components.
    $complete = ($inspected -eq $all.Count -and $failed.Count -eq 0)
    if ($complete) {
        $facts.spfx['components'] =
        New-ScalarFact -Value $components -RawField 'Get-PnPPageComponent'
        $facts.spfx['component_count'] =
        New-ScalarFact -Value $components.Count -RawField 'Get-PnPPageComponent'
    }
    else {
        $facts.spfx['components'] = [ordered]@{
            state  = 'partial'
            value  = $components
            detail = "$inspected of $($all.Count) pages inspected. No usage was observed in the pages inspected; that is not the same as no usage."
            raw    = [ordered]@{ field = 'Get-PnPPageComponent'; value = $components.Count }
        }
        $facts.spfx['component_count'] = [ordered]@{
            state  = 'partial'
            value  = $components.Count
            detail = "A lower bound: $inspected of $($all.Count) pages were opened."
            raw    = [ordered]@{ field = 'Get-PnPPageComponent'; value = $components.Count }
        }
    }
    return $facts
}

function Get-ModernityFacts {
    param($Web)

    $facts = [ordered]@{ web = [ordered]@{}; pages = [ordered]@{} }

    # How the site is built and branded. Every one of these is a property the
    # product returns; none of them is read as "modern" or "classic" here.
    # That reading belongs to a rule, next to a source.
    $map = [ordered]@{
        template          = 'WebTemplate'
        configuration     = 'Configuration'
        master_url        = 'MasterUrl'
        custom_master_url = 'CustomMasterUrl'
        alternate_css_url = 'AlternateCssUrl'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $Web.$property
            if ($null -eq $value) {
                $facts.web[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this web."
            }
            else {
                $facts.web[$name] = New-ScalarFact -Value ("$value") -RawField $property
            }
        }
        catch {
            $facts.web[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # The file, not the path. The path carries the site: on the root site the
    # master page reads `/_catalogs/masterpage/seattle.master`, and on
    # `/sites/finance` the same default master page reads
    # `/sites/finance/_catalogs/masterpage/seattle.master`. A rule comparing
    # the path against a known default would fire on every site that is not
    # the root, which is most of them.
    foreach ($pair in @(@{ from = 'master_url'; to = 'master_page_file' },
                        @{ from = 'custom_master_url'; to = 'custom_master_page_file' })) {
        $source = $facts.web[$pair.from]
        if ($source.state -eq 'observed' -and -not [string]::IsNullOrWhiteSpace($source.value)) {
            $facts.web[$pair.to] = New-ScalarFact `
                -Value ([string] (Split-Path -Leaf $source.value)) `
                -RawField "$($map[$pair.from]) (file)"
        }
        else {
            $facts.web[$pair.to] = New-AbsentFact -State $source.state `
                -Detail "Derived from $($pair.from), which was not read."
        }
    }

    # The feature ids that are enabled, as a list. Which id means what is a
    # documented claim, so it belongs in a rule with its source beside it,
    # not buried in a collector that nobody reviews for that.
    foreach ($pair in @(@{ name = 'web_feature_ids'; scope = 'Web' },
                        @{ name = 'site_feature_ids'; scope = 'Site' })) {
        try {
            $ids = @(Get-PnPFeature -Scope $pair.scope -ErrorAction Stop |
                    ForEach-Object { $_.DefinitionId.ToString().ToUpperInvariant() })
            $facts.web[$pair.name] = New-ScalarFact -Value $ids -RawField "Feature.DefinitionId ($($pair.scope))"
        }
        catch {
            $facts.web[$pair.name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # Pages. Two counts from two sources, and the difference between them is
    # derived only when both are complete.
    $modern = $null
    try {
        $modern = @(Get-PnPPage -ErrorAction Stop)
        $facts.pages['modern_observed'] =
        New-ScalarFact -Value $modern.Count -RawField 'Get-PnPPage'
    }
    catch {
        $facts.pages['modern_observed'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    $inLibrary = $null
    try {
        $library = Get-PnPList -Identity 'SitePages' -ErrorAction Stop
        $inLibrary = [int] $library.ItemCount
        $facts.pages['in_library'] =
        New-ScalarFact -Value $inLibrary -RawField 'SitePages.ItemCount'
    }
    catch {
        $facts.pages['in_library'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    # Not "classic pages". Pages in the library that Get-PnPPage did not
    # return, which is a different sentence: a page can be absent from that
    # list for reasons other than being classic, and this collector does not
    # know which. The name says what was counted.
    if ($null -ne $modern -and $null -ne $inLibrary) {
        $rest = $inLibrary - $modern.Count
        if ($rest -lt 0) { $rest = 0 }
        $facts.pages['in_library_not_returned_as_modern'] =
        New-ScalarFact -Value $rest -RawField 'SitePages.ItemCount - Get-PnPPage'
    }
    else {
        $facts.pages['in_library_not_returned_as_modern'] = New-AbsentFact `
            -State 'missing' -Detail 'Derived from two counts, and one was not read.'
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

# Sharing settings live on the tenant's record of a site, so that mode
# connects to the admin centre like TenantSites does.
$adminModes = @('TenantSites', 'SiteSharing')
$connectUrl = if ($adminModes -contains $Mode) { $TenantUrl } else { $SiteUrl }
if (-not $connectUrl) {
    $needed = if ($adminModes -contains $Mode) { '-TenantUrl' } else { '-SiteUrl' }
    throw "Mode $Mode needs $needed."
}
if ($Mode -eq 'SiteSharing' -and -not $SiteUrl) {
    throw 'Mode SiteSharing needs -SiteUrl as well as -TenantUrl.'
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
                    id = $SiteUrl; type = 'site'
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
                    id = "$SiteUrl::$ListTitle"; type = 'list'
                    display_name = $ListTitle; url = $SiteUrl
                }) `
                -Facts (Get-ListPermissionFacts -List $list) `
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

    'Modernity' {
        $web = Get-PnPWeb -Includes WebTemplate, Configuration, MasterUrl, `
            CustomMasterUrl, AlternateCssUrl
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    id = $SiteUrl; type = 'site'
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-ModernityFacts -Web $web) `
                -Requested @('web', 'pages') -Completed @('web', 'pages') `
                -Unavailable ([ordered]@{}))
    }

    'SpfxCatalog' {
        $scope = if ($TenantUrl) { 'Tenant' } else { 'Site' }
        $web = Get-PnPWeb
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    id = $SiteUrl; type = 'site'
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-SpfxCatalogFacts -Scope $scope) `
                -Requested @('spfx') -Completed @('spfx') -Unavailable ([ordered]@{}))
    }

    'SpfxPages' {
        $web = Get-PnPWeb
        Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
                -Resource ([ordered]@{
                    id = $SiteUrl; type = 'site'
                    display_name = [string] $web.Title; url = $SiteUrl
                }) `
                -Facts (Get-SpfxPageFacts) `
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
