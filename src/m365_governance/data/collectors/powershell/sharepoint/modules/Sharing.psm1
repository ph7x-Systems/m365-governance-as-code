<#
    Sharing.psm1

    What one site permits, and what the organisation permits.

    Two levels, one file, because they answer the same question at different
    scopes and are meant to be read together: a site that sets no default of
    its own inherits the tenant's.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1') -Force

function Get-SharingFacts {
    param($Site)

    # SharePoint enforces that a site cannot be more permissive than the
    # tenant, so both values are reported for context rather than for a rule
    # about one exceeding the other: that rule could never fire.
    $facts = [ordered]@{ sharing = [ordered]@{} }
    #
    # anonymous_link_expiry_override is collected BECAUSE the number beside it
    # cannot be read without it. The site's expiry figure is governed by
    # OverrideTenantAnonymousLinkExpirationPolicy, a Boolean: with the override
    # false the site is following the tenant, and its own number says nothing
    # about what is in force. Collecting the days without the flag is
    # collecting a value with no meaning, and it is why no rule reads the days
    # today. The cmdlet that writes either of them is deliberately not named
    # here: this file is read-only, and a test enforces that by pattern, which
    # is stricter than parsing comments and right to be.
    # See docs/COLLECTION-PATH-AUDIT.md.
    $map = [ordered]@{
        capability                     = 'SharingCapability'
        default_link_type              = 'DefaultSharingLinkType'
        default_link_permission        = 'DefaultLinkPermission'
        anonymous_link_expiry_days     = 'AnonymousLinkExpirationInDays'
        anonymous_link_expiry_override = 'OverrideTenantAnonymousLinkExpirationPolicy'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $Site.$property
            if ($null -eq $value -or "$value" -eq '') {
                $facts.sharing[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this site."
            }
            elseif ($name -eq 'anonymous_link_expiry_days') {
                $facts.sharing[$name] =
                New-ScalarFact -Value ([int] $value) -RawField $property
            }
            else {
                $facts.sharing[$name] =
                New-ScalarFact -Value ("$value") -RawField $property
            }
        }
        catch {
            $facts.sharing[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # `None` is not a link type. It is how a site says it sets no default of
    # its own and follows the tenant, and the tenant setting is not in this
    # document. Reported as observed, a rule comparing it against
    # AnonymousAccess would return `pass` while knowing nothing: the tenant
    # default it inherits could be exactly that.
    #
    # So the effective default is a separate fact, and it is missing when the
    # site inherits. The rule then answers `unknown`, which is the truth.
    $declared = $facts.sharing['default_link_type']
    if ($declared.state -eq 'observed' -and $declared.value -ne 'None') {
        $facts.sharing['effective_default_link_type'] =
        New-ScalarFact -Value $declared.value -RawField 'DefaultSharingLinkType'
    }
    elseif ($declared.state -eq 'observed') {
        $facts.sharing['effective_default_link_type'] = New-AbsentFact -State 'missing' `
            -Detail ('The site sets no default of its own and follows the tenant. ' +
                     'The tenant setting was not read by this collection.')
    }
    else {
        $facts.sharing['effective_default_link_type'] = New-AbsentFact `
            -State $declared.state -Detail 'Derived from the site setting, which was not read.'
    }
    return $facts
}

function Get-TenantSharingFacts {
    param($Tenant)

    # THE FACT AN EXISTING RULE SAYS IS MISSING.
    #
    # SPO-SHARE-002 already records, in its own limitations, that a site with
    # no default of its own follows the tenant and that "the tenant setting is
    # a separate fact this collection does not gather". This is that fact.
    #
    # THREE PROPERTIES, AND ONLY THREE. Eleven are available on the tenant, and
    # seven of them are described by Microsoft without being recommended: a
    # rule on those would be our convention wearing the clothes of documented
    # guidance. Collecting them anyway would be evidence with no reader, which
    # ages without anything going red. Every name below is consumed by a rule
    # in the same change. See docs/COLLECTION-PATH-AUDIT.md.
    #
    # Validated on the tenant cmdlet reference and on the anonymous-sharing
    # best practice page, both checked on 8 August 2026.
    $facts = [ordered]@{ tenant_sharing = [ordered]@{} }
    $map = [ordered]@{
        capability                 = 'SharingCapability'
        default_link_type          = 'DefaultSharingLinkType'
        file_anonymous_link_type   = 'FileAnonymousLinkType'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $Tenant.$property
            if ($null -eq $value -or "$value" -eq '') {
                $facts.tenant_sharing[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this tenant."
            }
            else {
                $facts.tenant_sharing[$name] = New-ScalarFact -Value ("$value") -RawField $property
            }
        }
        catch {
            $facts.tenant_sharing[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }
    return $facts
}

Export-ModuleMember -Function Get-SharingFacts, Get-TenantSharingFacts
