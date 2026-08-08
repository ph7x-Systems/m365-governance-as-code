# PSScriptAnalyzer configuration.
#
# Suppressions live here, each with the reason next to it, rather than as
# attributes buried in a function where nobody reviewing a diff would see them.
# The standard this enforces is written once, in docs/POWERSHELL-STANDARDS.md.

@{
    IncludeDefaultRules = $true

    # Error and Warning fail the build. Information does not: the only
    # informational finding here is PSProvideCommentHelp on internal functions
    # that have a comment block but not a `.SYNOPSIS` one. Comment-based help
    # exists so `Get-Help` can answer a user, and these functions have no user.
    Severity            = @('Error', 'Warning')

    ExcludeRules        = @(
        # The collector's progress lines are for a person watching a tenant
        # run, and Write-Host is documented as the cmdlet for exactly that:
        # "produce for-(host)-display-only output". Evidence never goes to the
        # host — it is written as JSON by Write-Evidence — so the rule's real
        # concern, data that cannot be captured or redirected, does not apply.
        # https://learn.microsoft.com/powershell/module/microsoft.powershell.utility/write-host
        'PSAvoidUsingWriteHost',

        # The four functions flagged are New-Unavailable, New-ScalarFact,
        # New-AbsentFact and New-Evidence, all in Evidence.psm1, and all of
        # them build a hashtable in memory. `New` is the approved verb for
        # constructing an object; the rule reads it as constructing a resource.
        # Nothing here changes anything a -WhatIf could decline. The one
        # function that touches a disk is Write-Evidence, which is named for it
        # and is the collector's entire purpose.
        'PSUseShouldProcessForStateChangingFunctions',

        # Get-SharingFacts, Get-OwnerFacts and their eight siblings return the
        # complete set of facts for one resource, not one fact. Get-SharingFact
        # would name something the function does not do. The guidance (SD01)
        # exists so users can predict a command name, and these are internal
        # functions with no user. Recorded in docs/POWERSHELL-STANDARDS.md
        # under "Deliberate divergence" rather than quietly ignored.
        'PSUseSingularNouns',

        # All twelve findings are continuation lines aligned under the
        # construct that opens them — an array of hashtables, or the arguments
        # of a call spread over several lines. The rule wants a fixed indent
        # step and cannot express alignment, so satisfying it here would mean
        # writing the less readable of two correct forms. Enabled rules that
        # can be satisfied are worth more than a disabled one; this one cannot.
        'PSUseConsistentIndentation'
    )

}
