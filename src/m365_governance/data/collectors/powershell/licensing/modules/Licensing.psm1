# public-scope-check: this file names the words it forbids. `trial` here is
# Microsoft's own `companySubscription.isTrial`, describing a TENANT's
# subscription, and it is governance evidence rather than this product's
# commercial model. The guard exists to stop pH7x pricing, entitlement and
# trial mechanics reaching a public MIT repository; a vendor field name that
# a collector must record is the opposite of that.
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

function Read-UsageReport {
    <#
        .SYNOPSIS
        What one usage report says about itself and its rows.

        .DESCRIPTION
        THE COLUMNS ARE MICROSOFT'S AND ARE NOT INVENTED HERE.
        `getOffice365ActiveUserDetail` returns one row per user with, among
        others, `Report Refresh Date`, `User Principal Name`, `Is Deleted`, a
        `Has ... License` column per service and a `... Last Activity Date` per
        service. This reads three things from it and concludes none of them:
        when the data was last rebuilt, how many rows came back, and how many of
        those rows name a principal rather than a concealed identifier.

        THE LAST ONE DECIDES WHAT THE REST IS WORTH. Where the tenant conceals
        identifiable information the principal column holds an opaque
        identifier, and a report of ten thousand such rows supports no statement
        about any person in it. A concealed identifier is recognised by shape --
        it carries no `@` -- rather than by asking the setting again, so the
        report is read on its own terms.
    #>
    param(
        [Parameter(Mandatory = $true)] [string] $Path,
        [Parameter(Mandatory = $true)] [string] $Report,
        [Parameter(Mandatory = $true)] [int] $WindowDays
    )

    $rows = @(Import-Csv -Path $Path)
    $named = @($rows | Where-Object {
            $upn = "$($_.'User Principal Name')"
            $upn -and $upn.Contains('@')
        }).Count

    $refresh = ''
    if ($rows.Count -gt 0) { $refresh = "$($rows[0].'Report Refresh Date')" }

    return [ordered]@{
        report                  = $Report
        window_days             = $WindowDays
        report_refresh_date     = $refresh
        rows                    = $rows.Count
        rows_naming_a_principal = $named
    }
}

function Get-SkuCapacity {
    <#
        .SYNOPSIS
        What kind of capacity each observed SKU represents, and whether its
        units may be added to another SKU's.

        .DESCRIPTION
        WHY THIS EXISTS. `units_purchased` was removed from this collector after
        it returned a seven-figure total on a tenant with a few dozen assigned
        seats. The number was arithmetically correct: it was the sum of
        `prepaidUnits.enabled` across every SKU the tenant holds. It was also
        meaningless, because those units do not all count the same thing.

        THE FIX IS NOT A BETTER FILTER. Dropping the SKUs whose numbers look
        absurd is the same error with a threshold in front of it: it decides
        what a tenant holds by how the figures look. What is needed is to know
        what each SKU IS, and to say `not established` where that is not known.

        WHAT MICROSOFT DOCUMENTS, and it is the whole basis for what follows:

          `appliesTo`         `User` or `Company`. ONLY SKUs whose target class
                              is `User` are assignable. A `Company` SKU's units
                              are not user seats and never were.

          `capabilityStatus`  `Enabled`, `Warning`, `Suspended`, `Deleted`,
                              `LockedOut`. Anything but `Enabled` is a
                              subscription that is expiring, cancelled or gone.

          `prepaidUnits`      four counters, one per lifecycle state. `enabled`
                              is the units enabled for the ACTIVE subscription.

        WHAT MICROSOFT DOES NOT PUT ON THIS SURFACE, and it is the reason
        nothing here is ever `comparable`:

          Whether the organisation BOUGHT the subscription, or a user signed
          themselves up for it under self-service, which Microsoft documents as
          provisioning services `without asking you to take action on their
          behalf`. A tenant holding a SKU does not mean the tenant purchased it.

          How many seats were bought. `prepaidUnits.enabled` is not that number.
          `companySubscription.totalLicenses` is, and `companySubscription.isTrial`
          says whether it was a purchase at all. That resource is reachable at
          `/directory/subscriptions`, in BETA only, and `subscribedSku.subscriptionIds`
          is the join to it.

        So this classifies what the read can settle, and names the measurement
        that would settle the rest. It never guesses, and it never excludes.
    #>
    param([array] $Skus, [array] $Join)

    $joined = @{}
    foreach ($row in @($Join)) { $joined[[string] $row.sku] = $row }

    $out = @()
    foreach ($sku in @($Skus)) {
        $kind = 'not-established'
        $eligibility = 'not-established'
        $because = @()

        $applies = [string] $sku.applies_to
        $status = [string] $sku.capability_status

        if ($applies -eq 'Company') {
            $kind = 'organisational'
            $eligibility = 'not-comparable'
            $because += 'appliesTo is Company, and Microsoft documents that only a SKU whose target class is User is assignable, so these units are not user seats'
        }
        elseif ($applies -eq 'User') {
            $kind = 'user-assignable'
            $because += 'appliesTo is User, which Microsoft documents as the only assignable target class'
        }
        else {
            $because += "appliesTo is '$applies', which is not a documented target class, so what these units count is not established"
        }

        if ($status -and $status -ne 'Enabled') {
            $eligibility = 'not-comparable'
            $because += "capabilityStatus is $status rather than Enabled, so this subscription is not current capacity"
        }

        # THE UNIT IS WHAT MAKES A NUMBER COMPARABLE, and seats are the unit.
        # `companySubscription.totalLicenses` is documented as the number of
        # seats included in a subscription, and a seat means the same thing on
        # every subscription that reports one. `prepaidUnits.enabled` does not,
        # which is why it was never a candidate.
        #
        # COMPARABLE IS NOT PURCHASED. What was bought is a separate question
        # this does not answer, and merging the two would put the removed total
        # back with a citation attached.
        $link = $joined[[string] $sku.sku]
        if ($eligibility -eq 'not-established') {
            if ($null -ne $link -and $link.state -eq 'joined' -and $kind -eq 'user-assignable') {
                $eligibility = 'comparable'
                $because += "seats are established from companySubscription.totalLicenses, and a seat is the same unit on every subscription that reports one"
                $because += 'this says the units may be added to another subscription seats, and says nothing about whether they were bought'
            }
            elseif ($null -ne $link -and $link.state -eq 'unmatched') {
                $because += 'the commercial subscriptions were read and none matched this SKU, so its seats are not established'
            }
            elseif ($null -ne $link -and $link.state -eq 'unsupported') {
                $because += 'the commercial subscription surface is not available here, so seats cannot be established'
            }
            else {
                $because += 'whether this is a trial and how many seats it carries are on companySubscription (isTrial, totalLicenses) at /directory/subscriptions, in the beta endpoint, which this run did not read'
            }
        }

        $row = [ordered]@{
            sku                     = [string] $sku.sku
            sku_id                  = [string] $sku.sku_id
            capacity_kind           = $kind
            aggregation_eligibility = $eligibility
            because                 = $because
        }
        if ($null -ne $link) {
            $row['subscription_state'] = [string] $link.state
            $row['commercial_basis'] = [string] $link.commercial_basis
            if ($link.Contains('seats')) { $row['seats'] = [int] $link.seats }
        }
        $out += $row
    }

    return $out
}


function Get-SubscriptionJoin {
    <#
        .SYNOPSIS
        The commercial subscriptions behind one SKU, and what the join settled.

        .DESCRIPTION
        THE SEAT COUNT IS NOT ON `subscribedSkus`. `prepaidUnits.enabled` is
        documented as the units enabled for the ACTIVE subscription, which is a
        different quantity from the seats a subscription carries. The seats are
        `companySubscription.totalLicenses`, documented as `the number of seats
        included in this subscription`, and `subscribedSku.subscriptionIds` is
        the join to them.

        THE RESOURCE IS BETA. `/directory/subscriptions` returns
        `companySubscription` and exists in the beta endpoint only, which
        Microsoft marks as subject to change and unsupported in production. That
        is a result about Microsoft Graph rather than about this engine, and it
        travels with every fact derived from it: the commercially authoritative
        surface for a tenant's own subscriptions is not in `v1.0`.

        `isTrial` DOES NOT ESTABLISH A PURCHASE, AND THIS IS THE TRAP.
        Microsoft documents it as `whether the subscription is a free trial or
        purchased`, which reads like a binary and is not one in a tenant. A
        self-service free programme is neither a trial nor a purchase: nobody
        bought it and it never expires. `isTrial` false therefore establishes
        `not a trial` and nothing more, and this collector says exactly that.
        Reading it as `purchased` would put the removed total back on the screen
        with a citation attached.

        WHAT THE JOIN DOES SETTLE is the unit. Seats mean the same thing on
        every subscription that reports them, so seats may be added to seats.
        What they may not be added into is a single figure called purchased
        capacity, and the commercial basis is carried separately so a consumer
        cannot merge them by accident.

        FIVE STATES, AND THEY ARE NOT ONE. `not-observed` is a run that did not
        ask. `unsupported` is a surface that answered that it does not exist
        here. `unmatched` is a SKU whose subscriptions were asked for and not
        found, which is evidence about this tenant. `joined` is the answer.
    #>
    param(
        [array] $Skus,
        [array] $Subscriptions,
        [string] $SurfaceState = 'not-observed'
    )

    $bySubscription = @{}
    foreach ($s in @($Subscriptions)) {
        if ($s.id) { $bySubscription[[string] $s.id] = $s }
    }

    $out = @()
    foreach ($sku in @($Skus)) {
        $ids = @($sku.subscription_ids | Where-Object { $_ })
        $matched = @()
        foreach ($id in $ids) {
            if ($bySubscription.ContainsKey([string] $id)) { $matched += $bySubscription[[string] $id] }
        }

        $state = $SurfaceState
        $seats = $null
        $basis = 'not-established'
        $because = @()

        if ($SurfaceState -eq 'observed') {
            if ($matched.Count -gt 0) {
                $state = 'joined'
                $seats = 0
                foreach ($m in $matched) { $seats += [int] $m.total_licenses }
                $because += "$($matched.Count) commercial subscription(s) matched on subscriptionIds, carrying $seats seat(s) in companySubscription.totalLicenses"

                $trials = @($matched | Where-Object { $_.is_trial -eq $true }).Count
                if ($trials -eq $matched.Count) {
                    $basis = 'trial'
                    $because += 'every matched subscription reports isTrial true'
                }
                elseif ($trials -eq 0) {
                    # NOT `purchased`. See the block comment above.
                    $basis = 'not-a-trial'
                    $because += 'no matched subscription reports isTrial true, which establishes that none of them is a trial and does not establish that any of them was bought'
                }
                else {
                    $basis = 'mixed'
                    $because += "$trials of $($matched.Count) matched subscriptions report isTrial true, so one basis does not describe this SKU"
                }
            }
            elseif ($ids.Count -gt 0) {
                $state = 'unmatched'
                $because += "$($ids.Count) subscriptionIds on this SKU matched no commercial subscription that was read, which is a fact about this tenant rather than a gap in the read"
            }
            else {
                $state = 'unmatched'
                $because += 'this SKU carries no subscriptionIds, so nothing links it to a commercial subscription'
            }
        }
        elseif ($SurfaceState -eq 'unsupported') {
            $because += 'the commercial subscription surface answered that it is not available here, so seats cannot be established'
        }
        else {
            $because += 'the commercial subscription surface at /directory/subscriptions was not read by this run'
        }

        $row = [ordered]@{
            sku              = [string] $sku.sku
            state            = $state
            commercial_basis = $basis
            because          = $because
        }
        if ($null -ne $seats) { $row['seats'] = $seats }
        $out += $row
    }

    return $out
}


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

        .PARAMETER Subscriptions
        The tenant's commercial subscriptions from `/directory/subscriptions`,
        when this run was authorized to read them. A separate surface, in the
        BETA endpoint, and the only one carrying seats and trial status.

        .PARAMETER SubscriptionSurface
        What happened to that surface: `not-observed`, `unsupported` or
        `observed`. Never inferred from the list being empty, because a tenant
        with no subscriptions and a run that did not ask return the same
        nothing.
    #>
    param(
        $SubscribedSkus,
        $Assignments,
        $ReportSettings,
        $UsageWindows,
        $Attempts,
        $Subscriptions,
        [string] $SubscriptionSurface = 'not-observed'
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
    # `units_purchased` USED TO BE HERE AND RETURNED A SEVEN-FIGURE TOTAL ON A
    # TENANT WITH A FEW DOZEN ASSIGNED SEATS. The number was arithmetically correct and
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
            -RawField 'subscribedSkus: skuPartNumber, skuId, appliesTo, capabilityStatus, prepaidUnits (four counters), consumedUnits, servicePlans, subscriptionIds'

        # THE COMMERCIAL SURFACE, RECORDED WHETHER OR NOT IT WAS READ. An
        # absent list and a list that came back empty are different facts.
        $l['subscription_surface'] = New-ScalarFact -Value $SubscriptionSurface `
            -RawField 'GET /beta/directory/subscriptions (companySubscription)'
        $l['subscription_surface_stability'] = New-ScalarFact -Value 'beta' `
            -RawField 'Microsoft Graph endpoint version for companySubscription'

        if ($SubscriptionSurface -eq 'observed') {
            $l['subscriptions'] = New-ScalarFact -Value @($Subscriptions) `
                -RawField 'directory/subscriptions: id, skuId, skuPartNumber, isTrial, totalLicenses, status'
        }
        else {
            if ($SubscriptionSurface -eq 'unsupported') {
                $absentState = 'not-supported'
                $absentDetail = 'The commercial subscription surface answered that it is not available here, so no seat count or trial status can be established.'
            }
            else {
                $absentState = 'missing'
                $absentDetail = 'This run did not read /directory/subscriptions, so no seat count or trial status was established.'
            }
            $l['subscriptions'] = New-AbsentFact -State $absentState -Detail $absentDetail
        }

        $join = @(Get-SubscriptionJoin -Skus $skus -Subscriptions $Subscriptions -SurfaceState $SubscriptionSurface)
        $l['subscription_join'] = New-ScalarFact -Value $join `
            -RawField 'subscribedSku.subscriptionIds against companySubscription.id'

        # WHAT EACH SKU IS, BEFORE ANYTHING IS ADDED TO ANYTHING. Never a
        # filter, and never a total: one row per SKU observed, each carrying the
        # documented rule that classified it.
        $capacity = @(Get-SkuCapacity -Skus $skus -Join $join)
        $l['sku_capacity'] = New-ScalarFact -Value $capacity `
            -RawField 'appliesTo, capabilityStatus and the commercial subscription join, per subscribedSku'

        # THE COUNTS ARE OF SKUs, NOT OF UNITS. A count of rows means the same
        # thing on every row; a sum of units does not, which is the whole
        # finding. `comparable` is currently zero by construction and that is
        # the result rather than a gap in the code: nothing on this surface
        # establishes that a SKU's units are purchased seats.
        $summary = [ordered]@{}
        foreach ($state in @('comparable', 'not-comparable', 'not-established')) {
            $summary[$state] = @($capacity | Where-Object { $_.aggregation_eligibility -eq $state }).Count
        }
        foreach ($kind in @('user-assignable', 'organisational', 'not-established')) {
            $summary["kind_$($kind -replace '-','_')"] = @($capacity | Where-Object { $_.capacity_kind -eq $kind }).Count
        }
        $l['capacity_summary'] = New-ScalarFact -Value $summary `
            -RawField 'count of subscribedSku rows per classification'

        # THE FIGURE EVERYBODY WANTS, AND IT IS SPLIT BY BASIS OR IT IS NOT
        # PUBLISHED. Seats may be added to seats. They may not be added into a
        # single number called purchased capacity, because `isTrial` false
        # establishes that a subscription is not a trial and does NOT establish
        # that anybody bought it: a self-service free programme is neither.
        # A SUM IS PUBLISHED ONLY WHERE THE GROUP MEANS ONE THING.
        #
        # THE JOIN MOVED THIS QUESTION AND DID NOT CLOSE IT. Seats are a
        # like-for-like unit, so `comparable` is right about the unit. But
        # `isTrial` false groups together a subscription somebody bought and a
        # self-service free programme nobody bought, and Microsoft documents the
        # field as distinguishing `a free trial or purchased` — a binary that a
        # tenant does not honour. A tenant holding a free Power BI allocation
        # reports a million seats under `isTrial: false`.
        #
        # Summing that group produces `1,010,500 seats` beside eight hundred
        # users, which is the removed total returned with a citation attached.
        # A mathematically correct number that induces a false reading is not
        # published as a figure, so the group carries its subscriptions and its
        # reason instead, and the seats stay on the rows where they are true.
        $comparable = @($capacity | Where-Object { $_.aggregation_eligibility -eq 'comparable' })
        if ($comparable.Count -gt 0) {
            $seats = [ordered]@{}
            foreach ($basis in @('trial', 'not-a-trial', 'mixed', 'not-established')) {
                $rows = @($comparable | Where-Object { $_.commercial_basis -eq $basis })
                $entry = [ordered]@{ subscriptions = $rows.Count }
                if ($basis -eq 'trial') {
                    $total = 0
                    foreach ($r in $rows) { $total += [int] $r.seats }
                    $entry['seats'] = $total
                }
                else {
                    $entry['seats_not_summed'] =
                        'isTrial false establishes that these are not trials and does not establish that any was bought: a self-service free programme is neither. Their seats are true on each row and their sum would be read as purchased capacity.'
                }
                $seats[$basis] = $entry
            }
            $l['comparable_capacity'] = New-ScalarFact -Value $seats `
                -RawField 'companySubscription.totalLicenses over comparable SKUs, summed only where the group means one thing'
        }
        else {
            $l['comparable_capacity'] = New-AbsentFact -State 'missing' `
                -Detail ('No SKU has an established seat count, so no comparable capacity is published. ' +
                         'The seats a subscription carries are companySubscription.totalLicenses and whether it is a trial is companySubscription.isTrial, ' +
                         'at /directory/subscriptions in the beta endpoint; subscribedSku.subscriptionIds is the join.')
        }

        # AND THE FIGURE NOBODY MAY PUBLISH. `prepaidUnits.enabled` is not seats
        # purchased, and neither is any total over it.
        $l['purchased_capacity'] = New-AbsentFact -State 'not-supported' `
            -Detail ('Not observable from these surfaces. companySubscription.isTrial distinguishes a free trial from a subscription that is not a trial; ' +
                     'it does not establish that an organisation bought one, because a self-service free programme is neither a trial nor a purchase. ' +
                     'Nothing read here says what was paid for.')
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
        # `@(...)` AROUND THE WHOLE PIPELINE, NOT ONLY AROUND ITS INPUT.
        # PowerShell unwraps a one-element result, so this emitted `7` for one
        # period and `[7, 30]` for two: the JSON TYPE of a published fact
        # changed with how many periods the caller asked for, and a consumer
        # parsing it as a number breaks on the second period while one parsing
        # it as a list breaks on the first. Found by comparing the first live
        # document against the fixture that was supposed to describe it -- the
        # fixture had the list and nothing had ever compared the two.
        $l['usage_window_days'] = New-ScalarFact `
            -Value @(@($UsageWindows) | ForEach-Object { [int] $_.window_days } |
                Sort-Object -Unique) `
            -RawField 'report period'

        # -- WHAT THE REPORT ITSELF SAYS ABOUT ITS OWN FRESHNESS --------------
        #
        # `Report Refresh Date` is a column, not something computed here. It is
        # the day the data behind the rows was last rebuilt, and Microsoft
        # publishes reports 24 to 72 hours behind, occasionally more. A run that
        # recorded only the period would let a reader treat a report built on
        # Monday as an answer about Wednesday.
        $refresh = @($UsageWindows | ForEach-Object { $_.report_refresh_date } |
            Where-Object { $_ } | Sort-Object -Unique)
        if ($refresh.Count -gt 0) {
            $l['usage_report_refresh_date'] = New-ScalarFact -Value $refresh `
                -RawField 'Report Refresh Date'
        }
        else {
            $l['usage_report_refresh_date'] = New-AbsentFact -State 'missing' `
                -Detail 'No report carried a refresh date.'
        }

        # -- HOW MANY ROWS, AND HOW MANY OF THEM NAME ANYBODY -----------------
        #
        # THE SECOND NUMBER IS THE ONE THAT DECIDES WHAT CAN BE CONCLUDED. A
        # report with ten thousand rows whose principal names are concealed
        # supports no statement about any person in it. Counting them separately
        # is the difference between `we have usage data` and `we have usage data
        # we may attribute`.
        $rows = 0; $named = 0
        foreach ($w in @($UsageWindows)) {
            $rows += [int] $w.rows
            $named += [int] $w.rows_naming_a_principal
        }
        $l['usage_rows'] = New-ScalarFact -Value $rows -RawField 'rows returned'
        $l['usage_rows_naming_a_principal'] = New-ScalarFact -Value $named `
            -RawField 'User Principal Name that is not a concealed identifier'
    }
    else {
        $l['usage_reports_read'] = New-AbsentFact -State 'missing' `
            -Detail 'No usage report was read by this run.'
        $l['usage_window_days'] = New-AbsentFact -State 'missing' `
            -Detail 'No usage report was read, so no window applies.'
        foreach ($name in @('usage_report_refresh_date', 'usage_rows',
                'usage_rows_naming_a_principal')) {
            $l[$name] = New-AbsentFact -State 'missing' `
                -Detail 'No usage report was read by this run.'
        }
    }

    # -- what would stop, if an assignment changed ---------------------------
    #
    # THE FIRST DEPENDENCY QUESTION THAT CAN BE ANSWERED WITHOUT GUESSING, and
    # it is answered at the level capability actually lives at. A SKU is a
    # bundle; a service plan is the thing somebody has. So for each person:
    #
    #   effective plans of an assignment
    #     = the SKU's plans, minus that assignment's disabled plans,
    #       keeping only `appliesTo = User` and `provisioningStatus = Success`
    #
    # A plan delivered by exactly ONE of a person's assignments is a capability
    # that disappears if that assignment is removed. A plan delivered by more
    # than one is not: another assignment already carries it.
    #
    # THIS IS A FACT AND NOT A RECOMMENDATION. Two SKUs delivering one plan may
    # differ in quota, in support, or in what the contract permits, none of
    # which is visible here. Whether an overlap means a licence can be removed
    # is a conclusion, it needs a declared basis, and it is not this collector's
    # to make.
    if ($null -ne $SubscribedSkus -and $null -ne $Assignments) {
        $plansBySku = @{}
        foreach ($sku in @($SubscribedSkus)) {
            if (-not $sku.Contains('service_plans')) { continue }
            $plansBySku[[string] $sku.sku_id] = @(
                @($sku.service_plans) | Where-Object {
                    $_.applies_to -eq 'User' -and $_.provisioning_status -eq 'Success'
                } | ForEach-Object { [string] $_.plan_id })
        }

        $soleSource = 0
        $alsoElsewhere = 0
        foreach ($person in @($Assignments)) {
            if (-not $person.Contains('licenses')) { continue }
            $delivered = @{}
            foreach ($held in @($person.licenses)) {
                $disabled = @($held.disabled_plans)
                foreach ($plan in @($plansBySku[[string] $held.sku_id])) {
                    if ($disabled -contains $plan) { continue }
                    $delivered[$plan] = 1 + [int] $delivered[$plan]
                }
            }
            foreach ($count in $delivered.Values) {
                if ($count -eq 1) { $soleSource++ } else { $alsoElsewhere++ }
            }
        }

        $l['plans_with_one_source'] = New-ScalarFact -Value $soleSource `
            -RawField 'servicePlans minus assignedLicenses.disabledPlans, per user'
        $l['plans_with_more_than_one_source'] = New-ScalarFact -Value $alsoElsewhere `
            -RawField 'servicePlans minus assignedLicenses.disabledPlans, per user'
    }
    else {
        foreach ($name in @('plans_with_one_source', 'plans_with_more_than_one_source')) {
            $l[$name] = New-AbsentFact -State 'missing' `
                -Detail ('Service plans and assignments were not both read, so ' +
                    'what a person would lose is not calculable.')
        }
    }

    # DEPENDENCY IS THE HALF NOTHING HERE READS, AND SAYING SO IS THE POINT.
    # A change needs usage and dependency. This collector reads what is assigned
    # and, at best, what was used. Recording the gap as a fact is what stops a
    # consumer reading a usage figure as an answer.
    $l['dependency_evidence'] = New-AbsentFact -State 'partial' `
        -Detail ('What one assignment uniquely delivers is calculable and is ' +
            'recorded: a ' +
            'service plan delivered by exactly one of a person assignments ' +
            'stops being delivered if that assignment is removed. What a ' +
            'capability is REQUIRED FOR -- a policy, a role, a compliance ' +
            'obligation, a workload that would stop -- is a different question ' +
            'and is not observable from an assignment or from usage. Nothing ' +
            'may be concluded about removing a licence without it.')

    return $facts
}

Export-ModuleMember -Function Get-LicensingFacts, Get-SkuCapacity, Get-SubscriptionJoin, Read-UsageReport
