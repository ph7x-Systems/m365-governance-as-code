<#
    Licensing.psm1

    WHAT IS ASSIGNED, WHAT IT CONTAINS, AND WHAT CAN BE OBSERVED BEING USED.

    This module answers that and stops. It concludes nothing, proposes nothing
    and costs nothing, because the question those need is not the one this
    collects: *what capability would disappear if this assignment changed*
    needs usage AND dependency, and this reads the first at best.

    TWO ACQUISITION SURFACES, AND THEY FAIL DIFFERENTLY. What is assigned comes
    from the directory and is enumerated: subscribed SKUs, per-user assignments,
    enabled and disabled service plans, all identifiable. Usage comes from the
    reports, which are neither enumerated nor queried -- they are REPORTED over
    a window, and the difference matters more here than anywhere else in this
    engine.

    THE CONSTRAINT THAT DECIDES WHETHER THIS CAPABILITY IS POSSIBLE AT ALL.
    Microsoft: *By default, all reports hide user information such as
    usernames, display names, groups, and sites to help companies support local
    privacy laws*, and *This setting also applies to the Microsoft 365 usage
    reports in Microsoft Graph*. So in a default tenant, usage evidence CANNOT
    BE JOINED TO A USER. Not partially, not approximately: the identifiers are
    concealed. A per-user licensing conclusion is impossible until an
    administrator has turned that off, and turning it off is itself *a logged
    event in the Microsoft Purview portal audit log*.

    `report_identifiability` is therefore the first fact this collects, before
    any count, because every downstream conclusion is conditional on it.

    THREE MORE PROPERTIES OF THE REPORTS, EACH ONE A WAY TO BE WRONG.
    They cover *the last 7, 30, 90, and 180 days*, so an absence is an absence
    within a window and never an absence. They *typically become available
    within 24 to 72 hours*, so the newest days are not there yet. And *when you
    delete a user account, Microsoft deletes that user's usage data within 30
    days* -- which removes the evidence exactly where a licensing conclusion
    would otherwise be strongest.

    AND THE JOIN MICROSOFT SAYS DOES NOT EXIST. *You can't generate a report
    where you enter a user's account and then get a list of which services they
    are using and how much.* The per-user cross-service view is assembled from
    per-service reports or it is not assembled, and this module records which
    services it actually has rather than implying a complete picture.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-LicensingFacts {
    <#
        .SYNOPSIS
        What is assigned, and the observability of its use, as facts.

        .PARAMETER SubscribedSkus
        What the tenant has bought, as returned by the directory.

        .PARAMETER Assignments
        Per-user license assignments, already enumerated.

        .PARAMETER ReportSettings
        The tenant's report privacy setting, which decides whether any of the
        usage evidence can be attributed to anybody.

        .PARAMETER UsageWindows
        Which service reports were read and over how many days.
    #>
    param(
        $SubscribedSkus,
        $Assignments,
        $ReportSettings,
        $UsageWindows,
        $Attempts
    )

    $facts = [ordered]@{ licensing = [ordered]@{} }
    $l = $facts.licensing

    # -- WHY SOMETHING IS NOT THERE, AND WHOSE LIMITATION IT IS ---------------
    #
    # `unavailable` ON ITS OWN IS TOO POOR A WORD WHEN THE REASON IS KNOWN.
    # A reader shown *usage unavailable* cannot tell these apart, and they are
    # not the same situation:
    #
    #   this version does not collect usage reports yet   -> our work, unbuilt
    #   this identity is not permitted to read them       -> the tenant's answer
    #   Microsoft does not expose it in this cloud        -> the vendor's answer
    #
    # The first is an incomplete product. The other two are facts about the
    # environment, and they are evidence. One visual bucket for both teaches a
    # reader that this product's gaps and the tenant's constraints look alike.
    #
    # `owner` is recorded per attempt and takes `implementation`,
    # `tenant-or-identity`, `microsoft` or `caller`. Only the first is work.
    if ($null -ne $Attempts) {
        $l['acquisition_attempts'] = New-ScalarFact -Value @($Attempts) `
            -RawField 'one record per acquisition surface this run tried'
    }
    else {
        $l['acquisition_attempts'] = New-AbsentFact -State 'missing' `
            -Detail 'This run recorded no acquisition attempts.'
    }

    # -- the population, before any number ------------------------------------
    $l['population'] = New-ScalarFact -Value 'entra-licensed-user-assignments' `
        -RawField 'directory enumeration of user license assignments'
    $l['acquisition_method'] = New-ScalarFact -Value 'enumerated' `
        -RawField 'directory'

    # WHAT A DIRECTORY READ CANNOT SEE. Microsoft states that the usage reports
    # do not cover every licensing model, and a capability granted outside this
    # tenant's own subscriptions is not an assignment in it. Both are absences
    # this read cannot tell apart from nothing being there.
    $l['populations_not_observed'] = New-ScalarFact `
        -Value @('non-subscription-license-models', 'assigned-outside-this-tenant') `
        -RawField 'not reachable from a directory read'

    # -- what is assigned ----------------------------------------------------------
    # PER SKU, AND NO TOTAL ACROSS THEM.
    #
    # `units_purchased` USED TO BE HERE AND WAS 1,130,062 ON A TENANT WITH
    # THIRTY-SEVEN ASSIGNED SEATS. The number was arithmetically correct and
    # meaningless: `prepaidUnits.enabled` counts something different on a paid
    # seat SKU and on a free or effectively unlimited one, and adding them
    # produces a figure nobody can act on and everybody can quote.
    #
    # IT IS NOT REPLACED BY A BETTER TOTAL. Choosing which SKUs are additive is
    # a classification this engine does not have and would be inventing, and an
    # aggregate somebody hand-filtered is the same failure with more steps. The
    # SKUs are published as Microsoft returned them, one row each, and a
    # consumer that needs a total has to say which rows it added.
    try {
        $skus = @($SubscribedSkus)
        $l['subscribed_skus'] = New-ScalarFact -Value $skus.Count -RawField 'subscribedSkus'
        $l['skus'] = New-ScalarFact -Value $skus `
            -RawField 'subscribedSkus: skuPartNumber, prepaidUnits.enabled, consumedUnits'
        $consumed = 0
        foreach ($s in $skus) { $consumed += [int] $s.consumed_units }
        # `consumedUnits` IS ADDITIVE AND THE OTHER IS NOT. It counts assignments,
        # which mean the same thing on every SKU: somebody holds it.
        $l['units_assigned'] = New-ScalarFact -Value $consumed -RawField 'consumedUnits'
    }
    catch {
        foreach ($name in @('subscribed_skus', 'skus', 'units_assigned')) {
            $l[$name] = New-AbsentFact -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    try {
        $rows = @($Assignments)
        $l['users_observed'] = New-ScalarFact -Value (@($rows | Select-Object -Unique user).Count) `
            -RawField 'directory enumeration'
        $l['assignments'] = New-ScalarFact -Value $rows.Count -RawField 'assignedLicenses'
        $plans = @($rows | ForEach-Object { $_.service_plans } | Select-Object -Unique)
        $l['service_plans_represented'] = New-ScalarFact -Value $plans.Count `
            -RawField 'assignedLicenses.servicePlans'
    }
    catch {
        foreach ($name in @('users_observed', 'assignments', 'service_plans_represented')) {
            $l[$name] = New-AbsentFact -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # -- whether usage can be attributed to anybody ---------------------------
    #
    # FIRST AMONG THE USAGE FACTS BECAUSE EVERY OTHER ONE IS CONDITIONAL ON IT.
    if ($null -ne $ReportSettings) {
        $concealed = [bool] $ReportSettings.display_concealed_names
        $l['report_identifiability'] = New-ScalarFact `
            -Value $(if ($concealed) { 'concealed' } else { 'identifiable' }) `
            -RawField 'adminReportSettings.displayConcealedNames'
    }
    else {
        $l['report_identifiability'] = New-AbsentFact -State 'missing' `
            -Detail ('The tenant report privacy setting was not read. Until it is, ' +
                'no usage figure below can be attributed to any user, because ' +
                'concealed is the default.')
    }

    if ($null -ne $UsageWindows) {
        $l['usage_reports_read'] = New-ScalarFact -Value @($UsageWindows).Count `
            -RawField 'getM365App/Email/OneDrive/SharePoint/Teams usage reports'
        $l['usage_window_days'] = New-ScalarFact `
            -Value (@($UsageWindows) | ForEach-Object { [int] $_.window_days } |
                Sort-Object -Unique) `
            -RawField 'report period'
    }
    else {
        $l['usage_reports_read'] = New-AbsentFact -State 'missing' `
            -Detail 'No usage report was read by this run.'
        $l['usage_window_days'] = New-AbsentFact -State 'missing' `
            -Detail 'No usage report was read, so no window applies.'
    }

    # DEPENDENCY IS THE HALF NOTHING HERE READS, AND SAYING SO IS THE POINT.
    # A change needs usage and dependency. This collector reads what is assigned
    # and, at best, what was used. Recording the gap as a fact is what stops a
    # consumer reading a usage figure as an answer.
    $l['dependency_evidence'] = New-AbsentFact -State 'missing' `
        -Detail ('No dependency evidence is collected by this run. What a ' +
            'capability is required for -- a policy, a role, a compliance ' +
            'obligation, a workload that would stop -- is not observable from ' +
            'an assignment or from usage, and nothing may be concluded without it.')

    return $facts
}

Export-ModuleMember -Function Get-LicensingFacts
