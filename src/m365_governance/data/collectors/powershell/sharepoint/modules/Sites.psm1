<#
    Sites.psm1

    The tenant inventory, one document per site.

    Storage figures come from the enumeration path, whose completeness is
    unproven; see docs/COLLECTION-PATH-AUDIT.md for why the rule that reads
    them is safe anyway.

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

Export-ModuleMember -Function Get-SiteInventoryFacts
