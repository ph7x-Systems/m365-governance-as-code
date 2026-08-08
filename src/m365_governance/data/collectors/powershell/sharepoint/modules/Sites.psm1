<#
    Sites.psm1

    The tenant inventory, one document per site.

    Everything here comes from the enumeration path, which Microsoft documents
    as not populating twenty-two named site properties. Every property mapped
    below is off that list, which is why storage agreed with the identity path
    on all five sandbox sites. See docs/COLLECTION-PATH-AUDIT.md.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1') -Force

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

    # `SharingCapability` is deliberately absent from the map above, and the
    # reason is documented rather than deduced from the symptom.
    #
    # Get-SPOSite's reference page states that when `-Limit` or `-Filter` is
    # used, twenty-two named site properties "will not be populated and may
    # contain a default value". `SharingCapability` is on that list.
    # Get-PnPTenantSite with no `-Identity` calls
    # `Tenant.GetSitePropertiesFromSharePointByFilters`, which is that path;
    # with `-Identity` it calls `GetSitePropertiesByUrl`, which is not.
    #
    # Reproduced on a tenant on 2026-08-08: one site in five returned
    # `Disabled` here, the zero member of the enum and so precisely the default
    # the documentation warns about, while the identity path returned
    # `ExternalUserAndGuestSharing` for the same site.
    #
    # The other four agreed, and that is not reassurance. The documentation
    # says *may*, so population is not guaranteed and nothing says which site
    # gets a real value on which call. So the property is recorded with a state
    # no rule can evaluate, and the detail says where the authoritative value
    # lives.
    #
    # Nothing else in the map above appears on the documented list, and
    # tests/test_collector.py fails if anything from it ever does.
    $facts.site['sharing_capability'] = New-AbsentFact -State 'not-supported' `
        -Detail ('Not evidence from this path. Get-SPOSite documents that ' +
                 'filtered enumeration does not populate SharingCapability ' +
                 'and may return a default; reproduced on 1 of 5 sites, ' +
                 '2026-08-08. Read sharing.capability from the identity path.')

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

Export-ModuleMember -Function Get-SiteInventoryFacts
