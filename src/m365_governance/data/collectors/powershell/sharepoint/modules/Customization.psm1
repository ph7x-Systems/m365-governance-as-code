<#
    Customization.psm1

    THE SURFACES BY WHICH EXECUTABLE CONTENT OR CUSTOMIZATION CAN REACH A PAGE.

    This module answers one question and refuses a wider one. It answers *what
    customization and page-execution control surfaces are observable on this
    site*. It does not answer *is this site safe*, and it does not answer *can
    no interactive content run here*: both are claims wider than these facts
    support, and the second is the exact conclusion the published article
    `/knowledge/sharepoint/what-custom-script-disabled-establishes/` exists to
    refuse.

    FOUR SURFACES, AND THIS MODULE IS ONE OF THEM. Configuration (the custom
    script setting), content (the Site Pages library and what is in it), the
    administrative execution path (SPFx and the app catalog, which `Spfx.psm1`
    owns) and browser runtime policy (CSP and strict file handling, which
    nothing here reads). They are different questions with different answers,
    and mixing them is how a reader ends up concluding one from another.

    WHY THE FACTS ARE SHAPED THIS WAY. Microsoft documents each of these
    controls as reaching less than its name suggests, and in two cases prints
    the limit itself: blocking custom script stops nine file extensions and
    `.html` is not among them, and preventing modern page creation *hides* the
    entry points while users *can still add pages from other modern pages*. So
    each fact here says what was read, and none of them says what it means.

    NOT REPEATED HERE: the count of items in the Site Pages library, which
    `Modernity.psm1` already collects as `pages.in_library`. One fact, one
    owner.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1')  # no -Force: see Activity.psm1

#: The Site Pages web feature. Removing it is how page creation is turned off
#: for one site, and Microsoft documents the removal through CSOM rather than
#: through a tenant property, which is why this is read as a feature and not as
#: a setting.
$script:SitePagesFeatureId = 'b6917cb1-93a0-4b97-a84d-7cf49975d4ec'

function Get-CustomizationFacts {
    param($Web, $TenantSite)

    $facts = [ordered]@{ customization = [ordered]@{} }
    $c = $facts.customization

    # -- what was read, and over what -----------------------------------------
    #
    # THE SAME DISCIPLINE THE OTHER FAMILIES CARRY, APPLIED HERE AFTER THE FACT.
    # This module was written before `population`, `acquisition_method` and
    # `populations_not_observed` existed, and an audit found it was the only
    # family without them. A reader of one family should not have to know which
    # week it was written in.
    $c['population'] = New-ScalarFact -Value 'sharepoint-site-customization-surfaces' `
        -RawField 'one site: its custom script state, Site Pages feature and library'
    $c['acquisition_method'] = New-ScalarFact -Value 'enumerated' `
        -RawField 'direct property and feature reads on this web'

    # WHAT THIS METHOD DOES NOT REACH, NAMED RATHER THAN LEFT TO BE INFERRED.
    # The tenant-level page creation setting is an admin centre read. Browser
    # runtime policy -- content security policy and strict file handling -- is
    # read by nothing in this engine, so its absence here says nothing about it.
    $c['populations_not_observed'] = New-ScalarFact `
        -Value @('tenant-page-creation-setting', 'browser-runtime-policy') `
        -RawField 'not reachable from a site-scoped read'

    # ── configuration ────────────────────────────────────────────────────────
    #
    # THE SETTING AND THE PERMISSION ARE TWO READS, NOT ONE. The setting is a
    # site property that only a tenant-scoped read returns; the permission is
    # what the setting operates through and any identity that can open the web
    # can see it. Collecting both is what lets a reader tell `blocked` from
    # `not observed`, which a single field cannot do.
    if ($null -ne $TenantSite) {
        try {
            # THE FACT IS NAMED FOR WHAT IT HOLDS, WHICH IS THE DENY FLAG.
            # It was `custom_script` carrying `DenyAddAndCustomizePages`, so a
            # reader who took it at its name had the meaning INVERTED: true
            # meant custom script is blocked. A rule written against the old
            # name would have reported every protected site as permissive. It
            # is the same defect as a field called `service_plans` that held
            # SKU identifiers, and it is caught the same way, by making the
            # name say which direction the boolean runs.
            #
            # IT IS NOT A BOOLEAN AND CASTING IT TO ONE IS ALWAYS TRUE.
            #
            # FOUND BY PROVOKING THE STATE IN A TENANT, and it could not have
            # been found any other way: `DenyAddAndCustomizePages` returns
            # `DenyAddAndCustomizePagesStatus`, an enum whose three values are
            # `Unknown`, `Disabled` and `Enabled`. `[bool]` on a non-empty
            # string is `$true`, so a site that PERMITS custom script was
            # collected as denying it, the rule passed, and the report said the
            # site was protected. Every hand-written fixture used real booleans
            # and agreed with the code.
            #
            # AND THE ENUM RUNS THE OTHER WAY AGAIN. `Enabled` means the DENY is
            # enabled, so custom script is blocked. `Disabled` means the deny is
            # off, so it is permitted. Two inversions stacked on one property.
            #
            # `Unknown` IS THE TENANT'S OWN THIRD ANSWER and is not coerced to
            # either side: a value the platform will not commit to is not a
            # finding about the site.
            $status = [string] $TenantSite.DenyAddAndCustomizePages
            switch ($status) {
                'Enabled' {
                    $c['custom_script_denied'] = New-ScalarFact -Value $true `
                        -RawField 'DenyAddAndCustomizePages'
                }
                'Disabled' {
                    $c['custom_script_denied'] = New-ScalarFact -Value $false `
                        -RawField 'DenyAddAndCustomizePages'
                }
                'Unknown' {
                    $c['custom_script_denied'] = New-AbsentFact -State 'missing' `
                        -Detail ('DenyAddAndCustomizePages returned Unknown, which is a ' +
                            'value of the status enum and not a failure to read. The ' +
                            'platform did not commit to an answer, so neither does this.')
                }
                default {
                    $c['custom_script_denied'] = New-AbsentFact -State 'invalid' `
                        -Detail ("DenyAddAndCustomizePages returned '$status', which is " +
                            'not one of the documented values Unknown, Disabled or ' +
                            'Enabled. A value this collector does not recognise is not ' +
                            'guessed at.')
                }
            }
        }
        catch {
            $c['custom_script_denied'] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }
    else {
        # NOT THE SAME AS ALLOWED, AND THE VOCABULARY CANNOT YET SAY WHICH.
        # The contract's collection states are `observed`, `missing`,
        # `not-supported`, `permission-denied`, `partial` and `invalid`. None of
        # them means *nobody asked*, so `missing` carries it and the detail says
        # what `missing` alone would hide. That gap is recorded for the owner in
        # outside this repository; until it is decided, the sentence is the only
        # thing keeping a read nobody made apart from a value nothing returned.
        $c['custom_script_denied'] = New-AbsentFact -State 'missing' `
            -Detail ('DenyAddAndCustomizePages is returned by a tenant-scoped ' +
                'read, and this run did not make one for this site. Not read is ' +
                'not the same as not set.')
    }

    # What the setting operates through, and readable by the identity that is
    # already here. `AddAndCustomizePages` absent from the effective permissions
    # is the mechanism by which nobody on this site can insert script.
    try {
        $web = Get-PnPWeb -Includes EffectiveBasePermissions -ErrorAction Stop
        $held = $web.EffectiveBasePermissions.Has('AddAndCustomizePages')
        $c['add_and_customize_pages_held'] = New-ScalarFact -Value ([bool] $held) `
            -RawField 'Web.EffectiveBasePermissions.AddAndCustomizePages'
    }
    catch {
        $c['add_and_customize_pages_held'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    # ── content surface ──────────────────────────────────────────────────────
    #
    # The Site Pages feature, which is what page creation is turned off by at
    # site level. Absent is a real answer and is not the same as unread.
    try {
        $features = @(Get-PnPFeature -Scope Web -ErrorAction Stop)
        $present = @($features | Where-Object {
                "$($_.DefinitionId)".ToLowerInvariant() -eq $script:SitePagesFeatureId
            }).Count -gt 0
        $c['site_pages_feature'] = New-ScalarFact -Value ([bool] $present) `
            -RawField "Get-PnPFeature -Scope Web ($script:SitePagesFeatureId)"
    }
    catch {
        $c['site_pages_feature'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    # The library itself, and whether somebody set permissions on it. Microsoft
    # names library permissions as what to use when the intent is to prevent
    # creation, which makes this the only one of these reads that describes
    # enforcement rather than an entry point.
    try {
        $library = Get-PnPList -Identity 'SitePages' -ErrorAction Stop
        $c['site_pages_library'] = New-ScalarFact -Value $true `
            -RawField 'Get-PnPList -Identity SitePages'
        try {
            $unique = $library.HasUniqueRoleAssignments
            $c['site_pages_unique_permissions'] = New-ScalarFact -Value ([bool] $unique) `
                -RawField 'SitePages.HasUniqueRoleAssignments'
        }
        catch {
            $c['site_pages_unique_permissions'] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }
    catch {
        # A site with no Site Pages library and a library this identity cannot
        # open return the same empty hand from a `try`. `Resolve-FailureState`
        # is what tells them apart, and it is why this is not written as $false.
        $c['site_pages_library'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        $c['site_pages_unique_permissions'] = New-AbsentFact -State 'missing' `
            -Detail 'The library was not read, so its permissions were not read either.'
    }

    return $facts
}

Export-ModuleMember -Function Get-CustomizationFacts
