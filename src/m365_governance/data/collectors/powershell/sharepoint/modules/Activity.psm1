<#
    Activity.psm1

    When a person last changed something.

    `LastItemUserModifiedDate`, not `LastItemModifiedDate`: on a real tenant
    every site had been touched that same day by a system process, and two of
    three had gone over a year without a person. That difference is the whole
    reason this module exists.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# NO `-Force` HERE, AND IT IS NOT A STYLE CHOICE.
#
# `-Force` on a module that is already loaded REMOVES it first, and the removal
# takes it out of the caller's scope too. `Get-SpoEvidence.ps1` imports Evidence
# and then imports this module; with `-Force` the second import unloaded the
# first, and the orchestrator lost `Initialize-Evidence`, `New-ScalarFact` and
# every other helper it had just imported. Every mode failed at the first call,
# on any tenant, with "The term 'Initialize-Evidence' is not recognized".
#
# Without `-Force` an already-loaded Evidence is reused and the caller keeps
# its own. Standalone import of this file still works: nothing is loaded yet,
# so the import happens normally.
Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1')

function Get-ActivityFacts {
    # TenantSiteError says why the tenant record is absent. It is mandatory
    # even though it is only used when TenantSite is $null: an absence with no
    # reason is the one thing the evidence model refuses, and a default here
    # would let a caller produce one by forgetting.
    param(
        $Web,
        $TenantSite,
        [Parameter(Mandatory = $true)] [string] $TenantSiteError
    )

    $facts = [ordered]@{ activity = [ordered]@{} }

    # Three dates, and the difference between them is the rule.
    #
    #   LastItemModifiedDate      moves when anything changes an item,
    #                             including a system process. A search crawl,
    #                             a retention job or a sync can keep it recent
    #                             on a site nobody has opened in two years.
    #   LastItemUserModifiedDate  moves when a person changes something.
    #   Created                   for the case of a site that never had a
    #                             first change to be older than.
    #
    # A rule about abandonment that reads the first one reports almost nothing,
    # and reports it confidently.
    $map = [ordered]@{
        last_item_modified      = 'LastItemModifiedDate'
        last_user_modified      = 'LastItemUserModifiedDate'
        created                 = 'Created'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $Web.$property
            if ($null -eq $value) {
                $facts.activity[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this web."
            }
            else {
                $facts.activity[$name] = New-ScalarFact `
                    -Value ([datetime] $value).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') `
                    -RawField $property
            }
        }
        catch {
            $facts.activity[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # A number, because the condition grammar compares numbers and not dates.
    # It is a function of when this collection ran, and the run time is in the
    # provenance beside it: the same evidence read a year later describes a
    # gap that was true on the day, not today.
    $userModified = $facts.activity['last_user_modified']
    if ($userModified.state -eq 'observed') {
        $days = [int] ([datetime]::UtcNow - [datetime] $userModified.value).TotalDays
        if ($days -lt 0) { $days = 0 }
        $facts.activity['days_since_user_change'] =
        New-ScalarFact -Value $days -RawField 'LastItemUserModifiedDate vs collected_at'
    }
    else {
        $facts.activity['days_since_user_change'] = New-AbsentFact `
            -State $userModified.state `
            -Detail 'Derived from LastItemUserModifiedDate, which was not read.'
    }

    # Whether anybody could have changed anything. A locked or archived site
    # with no recent change is not an abandoned site: it is a site somebody
    # decided about, and reporting the two together would bury the decision
    # among the accidents.
    foreach ($pair in @(@{ name = 'lock_state'; property = 'LockState' },
                        @{ name = 'archive_status'; property = 'ArchiveStatus' })) {
        if ($null -eq $TenantSite) {
            # The real reason, not a guess at it. On one site of three this
            # call failed while succeeding on the other two, and a message
            # saying "no administrative connection" would have described a
            # cause nobody had observed.
            $facts.activity[$pair.name] = New-AbsentFact -State 'missing' `
                -Detail ('The tenant record for this site was not read. ' +
                         $TenantSiteError)
            continue
        }
        try {
            $value = $TenantSite.($pair.property)
            if ($null -eq $value -or "$value" -eq '') {
                $facts.activity[$pair.name] = New-AbsentFact -State 'missing' `
                    -Detail "$($pair.property) was not returned for this site."
            }
            else {
                $facts.activity[$pair.name] =
                New-ScalarFact -Value ("$value") -RawField $pair.property
            }
        }
        catch {
            $facts.activity[$pair.name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }
    # Whether a person could have changed anything, from the two facts above.
    # A site nobody may write to and a site nobody wants are different
    # findings, and reporting them together buries the decision among the
    # accidents.
    $lock = $facts.activity['lock_state']
    $archive = $facts.activity['archive_status']
    if ($lock.state -eq 'observed' -and $archive.state -eq 'observed') {
        $open = ($lock.value -eq 'Unlock' -and $archive.value -eq 'NotArchived')
        $facts.activity['changeable'] =
        New-ScalarFact -Value $open -RawField 'LockState + ArchiveStatus'
    }
    else {
        $facts.activity['changeable'] = New-AbsentFact -State 'missing' `
            -Detail 'Derived from LockState and ArchiveStatus, and one was not read.'
    }
    return $facts
}

Export-ModuleMember -Function Get-ActivityFacts
