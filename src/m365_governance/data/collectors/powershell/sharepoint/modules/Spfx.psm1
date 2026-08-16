<#
    Spfx.psm1

    The app catalog, and the pages that host client-side parts.

    Page inspection is bounded and says so. A count that does not reconcile is
    marked `invalid` rather than published as arithmetic that cannot be true.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1')  # no -Force: see Activity.psm1

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
    # Both bounds are in the signature for the same reason as in
    # Permissions.psm1: a caller has to know the count is capped, and a module
    # cannot read the entry point's parameters anyway.
    param(
        [int] $MaxPages = 100,
        [datetime] $ModifiedSince
    )
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

Export-ModuleMember -Function Get-SpfxCatalogFacts, Get-SpfxPageFacts
