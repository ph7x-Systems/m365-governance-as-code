Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

<#
    SiteGuests.psm1

    Which guest accounts appear in a site's own list of users.

    WHAT THIS IS, EXACTLY. Every site keeps a list of the principals it has
    met: people who were granted something, people a link was sent to, people
    who opened the site through a group. This reads that list and keeps the
    entries that are guests.

    BEING IN THE LIST IS NOT HAVING ACCESS. An entry stays after a permission
    is removed, and a guest reached through a group may hold access without
    an entry of their own. So this establishes that a site has met a guest,
    which is the strongest thing the list can say, and nothing here may be
    read as what that guest can open today.

    AN IDENTIFIER AND NEVER A NAME. For each guest only the directory object
    identifier is kept, which is what joins a site to the directory's own
    record of the same account. The login name, the display name and the mail
    address are read to decide whether an entry is a guest and are written
    nowhere. A guest with no directory account -- somebody who opens a link
    with a one-time code -- has no identifier and is counted apart.

    Source: Get-PnPUser, PnP.PowerShell 3.4.1. Checked 12 November 2026.
#>

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1')  # no -Force: see Activity.psm1

function Get-SiteGuestFacts {
    try {
        $users = @(Get-PnPUser -Includes AadObjectId, IsShareByEmailGuestUser, IsEmailAuthenticationGuestUser -ErrorAction Stop)
    }
    catch {
        $state = Resolve-FailureState $_
        return @{
            facts       = @{ site_guests = [ordered]@{
                    guests = New-AbsentFact -State $state -Detail $_.Exception.Message
                }
            }
            unavailable = New-Unavailable -State $state -Detail $_.Exception.Message
        }
    }

    $identifiers = @()
    $without = 0
    foreach ($user in $users) {
        $login = [string] $user.LoginName
        $guest = ($login -like '*#ext#*') -or
            [bool] $user.IsShareByEmailGuestUser -or
            [bool] $user.IsEmailAuthenticationGuestUser
        if (-not $guest) { continue }
        $id = $null
        try { $id = [string] $user.AadObjectId.NameId } catch { $id = $null }
        if ($id) { $identifiers += $id.ToLowerInvariant() }
        else { $without++ }
    }
    $identifiers = @($identifiers | Sort-Object -Unique)

    return @{
        facts       = @{ site_guests = [ordered]@{
                guests                  = New-ScalarFact -Value ($identifiers.Count + $without) `
                    -RawField 'Get-PnPUser | Where-Object guest | Measure-Object'
                directory_guests        = New-ScalarFact -Value $identifiers.Count `
                    -RawField 'AadObjectId.NameId | Measure-Object'
                guest_object_ids        = New-ScalarFact -Value @($identifiers) `
                    -RawField 'AadObjectId.NameId'
                guests_without_account  = New-ScalarFact -Value $without `
                    -RawField 'guest entries with no AadObjectId'
            }
        }
        unavailable = $null
    }
}

Export-ModuleMember -Function Get-SiteGuestFacts
