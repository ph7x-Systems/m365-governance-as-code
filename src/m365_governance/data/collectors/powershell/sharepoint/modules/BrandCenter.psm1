<#
.SYNOPSIS
    The organisation's brand assets, and the boundary they are published across.

.DESCRIPTION
    THE ACL AND THE DISTRIBUTION BOUNDARY ARE TWO DIFFERENT THINGS, and this
    family exists because a reader who knows only the first will get the second
    wrong.

    A brand centre stores assets in a SharePoint Organization Asset Library, on
    a site with permissions like any other. Microsoft states that the brand
    centre REQUIRES Public CDN, and about a public origin it says: "Content in
    public origins within the Microsoft 365 CDN is accessible anonymously, and
    can be accessed by anyone who has URLs to hosted assets." So the site's
    permissions govern who can MANAGE the assets, and they do not govern who
    can FETCH them.

    Nothing here concludes. There is no rule in this family, because the
    question "should this organisation publish its logo anonymously" has no
    answer Microsoft publishes and no answer this engine may invent: publishing
    a logo to a public CDN is the intended design, and publishing something
    else there is a decision only the organisation can make. What the collector
    does is make the boundary visible instead of leaving it to be inferred from
    a site's permissions.

    `brand_center_configured` is never `brand_center_secure`, for the same
    reason `custom_script_denied` was never "nothing executable can run".
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-CdnStateFact {
    <#
        Public and private are separate switches with separate consequences, and
        a tenant may run either, both or neither. `Get-PnPTenantCdnEnabled`
        answers per type, so it is asked per type rather than once.
    #>
    param([Parameter(Mandatory)][ValidateSet('Public', 'Private')][string] $CdnType)

    try {
        $state = Get-PnPTenantCdnEnabled -CdnType $CdnType -ErrorAction Stop
        return New-ScalarFact -Value ([bool] $state) -RawField "Get-PnPTenantCdnEnabled -CdnType $CdnType"
    }
    catch {
        return New-AbsentFact -State 'permission-denied' -Detail (
            "The $($CdnType.ToLower()) CDN state was not readable by this identity: " +
            $_.Exception.Message)
    }
}

function Get-CdnOriginsFact {
    <#
        WHAT IS ACTUALLY PUBLISHED, which is not what the brand centre app
        shows. An origin is a library or folder whose eligible assets are
        replicated to the CDN, and a tenant may have origins that predate the
        brand centre or have nothing to do with it.
    #>
    param([Parameter(Mandatory)][ValidateSet('Public', 'Private')][string] $CdnType)

    try {
        $origins = @(Get-PnPTenantCdnOrigin -CdnType $CdnType -ErrorAction Stop)
        return New-ScalarFact -Value ([string[]] $origins) -RawField "Get-PnPTenantCdnOrigin -CdnType $CdnType"
    }
    catch {
        return New-AbsentFact -State 'permission-denied' -Detail (
            "The $($CdnType.ToLower()) CDN origins were not readable by this identity: " +
            $_.Exception.Message)
    }
}

function Get-CdnPolicyFacts {
    <#
        The three policies, and the third is the interesting one.

        `IncludeFileExtensions` is what may be served at all. Microsoft
        documents the defaults as different between public and private.

        `ExcludeRestrictedSiteClassifications` is the organisation saying some
        classifications never reach the CDN. Empty by default, which means no
        classification is excluded rather than that none exists.

        `ExcludeIfNoScriptDisabled` TIES THIS FAMILY TO CUSTOM SCRIPT. It
        excludes content based on the site-level NoScript attribute, which is
        the same `DenyAddAndCustomizePages` that `SPO-SCRIPT-001` reads. Two
        controls this engine already models, joined by a third nobody looks at.
    #>
    param([Parameter(Mandatory)][ValidateSet('Public', 'Private')][string] $CdnType)

    $facts = [ordered]@{}
    try {
        $policies = Get-PnPTenantCdnPolicies -CdnType $CdnType -ErrorAction Stop
        foreach ($name in @('IncludeFileExtensions', 'ExcludeRestrictedSiteClassifications', 'ExcludeIfNoScriptDisabled')) {
            $key = ($name -creplace '([a-z0-9])([A-Z])', '$1_$2').ToLower()
            if ($policies.ContainsKey($name)) {
                $facts[$key] = New-ScalarFact -Value ([string] $policies[$name]) -RawField $name
            }
            else {
                $facts[$key] = New-AbsentFact -State 'missing' -Detail (
                    "$name was not returned by Get-PnPTenantCdnPolicies for the " +
                    "$($CdnType.ToLower()) CDN. Absent is not empty: an empty policy is a " +
                    'policy that excludes nothing, and a missing one is a reading that did not happen.')
            }
        }
    }
    catch {
        foreach ($key in @('include_file_extensions', 'exclude_restricted_site_classifications', 'exclude_if_no_script_disabled')) {
            $facts[$key] = New-AbsentFact -State 'permission-denied' -Detail (
                "The $($CdnType.ToLower()) CDN policies were not readable by this identity: " +
                $_.Exception.Message)
        }
    }
    return $facts
}

function Get-BrandCenterFacts {
    <#
        One resource: the tenant. A brand centre is singular by design --
        Microsoft states the SharePoint brand centre "currently only allows one
        brand center for your organization" and creates it "in the primary geo
        of a tenant".
    #>
    param()

    $b = [ordered]@{}

    # THE LIBRARIES, WHICH ARE THE THING THE BRAND CENTRE IS BUILT ON. A tenant
    # may use organisation assets without ever enabling a brand centre, so the
    # presence of libraries is not the presence of a brand centre and is
    # reported as what it is.
    try {
        $libraries = @(Get-PnPOrgAssetsLibrary -ErrorAction Stop)
        $b['organization_asset_libraries'] = New-ScalarFact -Value $libraries.Count `
            -RawField 'Get-PnPOrgAssetsLibrary'
        $b['organization_asset_library_urls'] = New-ScalarFact `
            -Value ([string[]] ($libraries | ForEach-Object { [string] $_ })) `
            -RawField 'Get-PnPOrgAssetsLibrary'
    }
    catch {
        $b['organization_asset_libraries'] = New-AbsentFact -State 'permission-denied' -Detail (
            'The organisation asset libraries were not readable by this identity: ' +
            $_.Exception.Message)
        $b['organization_asset_library_urls'] = New-AbsentFact -State 'permission-denied' -Detail (
            'Not read, because the libraries themselves were not readable.')
    }

    $b['public_cdn_enabled'] = Get-CdnStateFact -CdnType 'Public'
    $b['private_cdn_enabled'] = Get-CdnStateFact -CdnType 'Private'
    $b['public_cdn_origins'] = Get-CdnOriginsFact -CdnType 'Public'
    $b['private_cdn_origins'] = Get-CdnOriginsFact -CdnType 'Private'

    foreach ($entry in (Get-CdnPolicyFacts -CdnType 'Public').GetEnumerator()) {
        $b["public_cdn_$($entry.Key)"] = $entry.Value
    }

    # WHAT AN ANONYMOUS FETCH MEANS HERE, carried as evidence rather than left
    # for a reader to remember. Microsoft: "Assets exposed in a public origin
    # are accessible by everyone anonymously."
    $b['public_origin_access'] = New-ScalarFact -Value 'anonymous' `
        -RawField 'documented: content in public origins is accessible anonymously'

    # AND REMOVAL IS NOT REMOVAL, which is the fact that turns a mistake into a
    # month. Microsoft: "If you remove an asset from a public origin, the asset
    # might continue to be available for up to 30 days from the cache; however,
    # we invalidate links to the asset in the CDN within 15 minutes."
    $b['public_origin_removal_persists_days'] = New-ScalarFact -Value 30 `
        -RawField 'documented: an asset removed from a public origin may remain available from cache for up to 30 days'

    # NOT OBSERVED FROM HERE, and named so an absence is not read as a nil.
    $b['brand_center_site'] = New-AbsentFact -State 'not-supported' -Detail (
        'Which site hosts the brand centre app is set in the Microsoft 365 admin centre ' +
        'and is not exposed by the SharePoint administration surface this collector reads. ' +
        'The organisation asset libraries above are what the brand centre is built on, and ' +
        'a tenant may use them without having enabled a brand centre.')
    $b['brand_managers'] = New-AbsentFact -State 'not-supported' -Detail (
        'Brand managers are the site owners of the brand centre site. Reading them is a ' +
        'site-scoped permission read against a site this collector was not pointed at, ' +
        'not a tenant property.')

    return [ordered]@{ brand_center = $b }
}

Export-ModuleMember -Function Get-BrandCenterFacts
