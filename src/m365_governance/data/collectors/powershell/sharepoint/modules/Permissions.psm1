<#
    Permissions.psm1

    Who administers a site, and which lists break inheritance.

    Group expansion is not attempted. A group owner is one principal and may
    be forty people, so this emits `expansion_complete = false` and a
    `minimum_count` rather than a count it cannot prove.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1')  # sem -Force: ver Activity.psm1

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
    # The bounds used to be read from the entry point's parameters, which a
    # module cannot see. Passing them in is not only what makes this work: it
    # puts the cap in the signature, where somebody reading the function can
    # find out that the count is bounded.
    param(
        $List,
        [switch] $CountUniqueScopes,
        [int] $MaxItemsPerList = 20000
    )

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

Export-ModuleMember -Function Get-OwnerFacts, Get-ListPermissionFacts
