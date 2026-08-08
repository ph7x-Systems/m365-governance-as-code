<#
    Modernity.psm1

    Template, branding, publishing.

    `CustomMasterUrl` is set on every site to the product default and the path
    carries the site, so comparing paths reported every non-root site.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1') -Force

function Get-ModernityFacts {
    param($Web)

    $facts = [ordered]@{ web = [ordered]@{}; pages = [ordered]@{} }

    # How the site is built and branded. Every one of these is a property the
    # product returns; none of them is read as "modern" or "classic" here.
    # That reading belongs to a rule, next to a source.
    $map = [ordered]@{
        template          = 'WebTemplate'
        configuration     = 'Configuration'
        master_url        = 'MasterUrl'
        custom_master_url = 'CustomMasterUrl'
        alternate_css_url = 'AlternateCssUrl'
    }
    foreach ($name in $map.Keys) {
        $property = $map[$name]
        try {
            $value = $Web.$property
            if ($null -eq $value) {
                $facts.web[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this web."
            }
            else {
                $facts.web[$name] = New-ScalarFact -Value ("$value") -RawField $property
            }
        }
        catch {
            $facts.web[$name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # The file, not the path. The path carries the site: on the root site the
    # master page reads `/_catalogs/masterpage/seattle.master`, and on
    # `/sites/finance` the same default master page reads
    # `/sites/finance/_catalogs/masterpage/seattle.master`. A rule comparing
    # the path against a known default would fire on every site that is not
    # the root, which is most of them.
    foreach ($pair in @(@{ from = 'master_url'; to = 'master_page_file' },
                        @{ from = 'custom_master_url'; to = 'custom_master_page_file' })) {
        $source = $facts.web[$pair.from]
        if ($source.state -eq 'observed' -and -not [string]::IsNullOrWhiteSpace($source.value)) {
            $facts.web[$pair.to] = New-ScalarFact `
                -Value ([string] (Split-Path -Leaf $source.value)) `
                -RawField "$($map[$pair.from]) (file)"
        }
        else {
            $facts.web[$pair.to] = New-AbsentFact -State $source.state `
                -Detail "Derived from $($pair.from), which was not read."
        }
    }

    # The feature ids that are enabled, as a list. Which id means what is a
    # documented claim, so it belongs in a rule with its source beside it,
    # not buried in a collector that nobody reviews for that.
    foreach ($pair in @(@{ name = 'web_feature_ids'; scope = 'Web' },
                        @{ name = 'site_feature_ids'; scope = 'Site' })) {
        try {
            $ids = @(Get-PnPFeature -Scope $pair.scope -ErrorAction Stop |
                    ForEach-Object { $_.DefinitionId.ToString().ToUpperInvariant() })
            $facts.web[$pair.name] = New-ScalarFact -Value $ids -RawField "Feature.DefinitionId ($($pair.scope))"
        }
        catch {
            $facts.web[$pair.name] = New-AbsentFact `
                -State (Resolve-FailureState $_) -Detail $_.Exception.Message
        }
    }

    # Pages. Two counts from two sources, and the difference between them is
    # derived only when both are complete.
    $modern = $null
    try {
        $modern = @(Get-PnPPage -ErrorAction Stop)
        $facts.pages['modern_observed'] =
        New-ScalarFact -Value $modern.Count -RawField 'Get-PnPPage'
    }
    catch {
        $facts.pages['modern_observed'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    $inLibrary = $null
    try {
        $library = Get-PnPList -Identity 'SitePages' -ErrorAction Stop
        $inLibrary = [int] $library.ItemCount
        $facts.pages['in_library'] =
        New-ScalarFact -Value $inLibrary -RawField 'SitePages.ItemCount'
    }
    catch {
        $facts.pages['in_library'] = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    # Not "classic pages". Pages in the library that Get-PnPPage did not
    # return, which is a different sentence: a page can be absent from that
    # list for reasons other than being classic, and this collector does not
    # know which. The name says what was counted.
    if ($null -ne $modern -and $null -ne $inLibrary) {
        $rest = $inLibrary - $modern.Count
        if ($rest -lt 0) { $rest = 0 }
        $facts.pages['in_library_not_returned_as_modern'] =
        New-ScalarFact -Value $rest -RawField 'SitePages.ItemCount - Get-PnPPage'
    }
    else {
        $facts.pages['in_library_not_returned_as_modern'] = New-AbsentFact `
            -State 'missing' -Detail 'Derived from two counts, and one was not read.'
    }
    return $facts
}

Export-ModuleMember -Function Get-ModernityFacts
