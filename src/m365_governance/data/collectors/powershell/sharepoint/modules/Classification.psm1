<#
    Classification.psm1

    What a site records about the kind of content it holds.

    An empty `SensitivityLabelId` is an observation, not a gap.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1') -Force

function Get-ClassificationFacts {
    param($Site)

    $facts = [ordered]@{ classification = [ordered]@{} }

    # An empty label is an observation, not a gap.
    #
    # The first version of this function reported an empty SensitivityLabelId
    # as `missing`, which said "the collector did not obtain this fact". Run
    # against a tenant, all three sites came back that way and the derived
    # `classified` fact was false: an answer built out of three admissions of
    # ignorance. Whichever of the two was right, the pair could not both be.
    #
    # The distinction the product actually offers is between a property that
    # loaded and a property that did not. -Includes either hydrates it or the
    # access throws. A hydrated property that is empty is SharePoint saying
    # there is no label, which is a fact a rule may act on. Only the throw is
    # a gap, and it keeps its own state below.
    function Read-Property([scriptblock] $Get) {
        try {
            $v = & $Get
            if ([string]::IsNullOrWhiteSpace("$v")) { return @{ ok = $true; value = $null } }
            return @{ ok = $true; value = "$v" }
        }
        catch {
            return @{ ok = $false; state = (Resolve-FailureState $_); detail = $_.Exception.Message }
        }
    }

    $info = $null
    try { $info = $Site.SensitivityLabelInfo } catch { $info = $null }

    $label = Read-Property { if ($info) { $info.Id } else { $Site.SensitivityLabelId } }
    $name = Read-Property { if ($info) { $info.DisplayName } }
    $class = Read-Property { $Site.Classification }
    $group = Read-Property { $Site.GroupId }

    # Whether a label is applied. Observed whenever the property loaded, and
    # false is as much an answer as true.
    if ($label.ok) {
        $facts.classification['label_applied'] =
        New-ScalarFact -Value ($null -ne $label.value) -RawField 'SensitivityLabelInfo.Id'
    }
    else {
        $facts.classification['label_applied'] =
        New-AbsentFact -State $label.state -Detail $label.detail
    }

    if ($label.ok -and $label.value) {
        $facts.classification['label_id'] = New-ScalarFact -Value $label.value -RawField 'SensitivityLabelInfo.Id'
    }
    elseif ($label.ok) {
        $facts.classification['label_id'] = New-AbsentFact -State 'missing' `
            -Detail 'No sensitivity label is applied to this site, so there is no id to report.'
    }
    else {
        $facts.classification['label_id'] = New-AbsentFact -State $label.state -Detail $label.detail
    }

    # The name is a separate fact from the id, and it is the one that goes
    # missing. The id is stored on the site; the name lives in the compliance
    # centre, and an identity that can read the first cannot always read the
    # second. A site labelled with a GUID nobody can name is classified, and
    # no report built from this evidence can say as what.
    if ($name.ok -and $name.value) {
        $facts.classification['label_name'] = New-ScalarFact -Value $name.value -RawField 'SensitivityLabelInfo.DisplayName'
    }
    elseif ($label.ok -and -not $label.value) {
        $facts.classification['label_name'] = New-AbsentFact -State 'missing' `
            -Detail 'No sensitivity label is applied, so there is no name to resolve.'
    }
    elseif ($name.ok) {
        $facts.classification['label_name'] = New-AbsentFact -State 'missing' `
            -Detail 'A label is applied and SharePoint returned no display name for it.'
    }
    else {
        $facts.classification['label_name'] = New-AbsentFact -State $name.state -Detail $name.detail
    }

    if ($label.ok -and $label.value -and $name.ok) {
        $facts.classification['label_resolved'] =
        New-ScalarFact -Value ($null -ne $name.value) -RawField 'SensitivityLabelInfo.DisplayName'
    }
    elseif ($label.ok -and -not $label.value) {
        $facts.classification['label_resolved'] = New-AbsentFact -State 'missing' `
            -Detail 'No label is applied, so there is nothing to resolve.'
    }
    else {
        $unread = if ($label.ok) { $name.state } else { $label.state }
        $facts.classification['label_resolved'] = New-AbsentFact -State $unread `
            -Detail 'Whether the label resolves to a name is not known, because the label itself was not read.'
    }

    # The older classification string. Superseded by sensitivity labels and
    # still set on sites that predate them, which is why it is a fact of its
    # own rather than a fallback folded into the label.
    if ($class.ok) {
        $facts.classification['classification_set'] =
        New-ScalarFact -Value ($null -ne $class.value) -RawField 'Classification'
        if ($class.value) {
            $facts.classification['site_classification'] =
            New-ScalarFact -Value $class.value -RawField 'Classification'
        }
        else {
            $facts.classification['site_classification'] = New-AbsentFact -State 'missing' `
                -Detail 'No classification string is set on this site.'
        }
    }
    else {
        $facts.classification['classification_set'] = New-AbsentFact -State $class.state -Detail $class.detail
        $facts.classification['site_classification'] = New-AbsentFact -State $class.state -Detail $class.detail
    }

    # Group-connected, from the site itself. The tenant record carries
    # IsTeamsConnected as well, and this mode does not read it: PnP refuses to
    # switch to the administration context after a device login, and a second
    # connection for one boolean is not worth the login. GroupId answers the
    # weaker question without any administrative right at all, and a
    # Teams-connected site is a group-connected site.
    $empty = '00000000-0000-0000-0000-000000000000'
    if ($group.ok) {
        $connected = ($null -ne $group.value -and $group.value -ne $empty)
        $facts.classification['group_connected'] = New-ScalarFact -Value $connected -RawField 'GroupId'
        if ($connected) {
            $facts.classification['group_id'] = New-ScalarFact -Value $group.value -RawField 'GroupId'
        }
        else {
            $facts.classification['group_id'] = New-AbsentFact -State 'missing' `
                -Detail 'This site is not connected to a Microsoft 365 group.'
        }
    }
    else {
        $facts.classification['group_connected'] = New-AbsentFact -State $group.state -Detail $group.detail
        $facts.classification['group_id'] = New-AbsentFact -State $group.state -Detail $group.detail
    }

    $facts.classification['teams_connected'] = New-AbsentFact -State 'not-supported' `
        -Detail ('IsTeamsConnected is a property of the tenant record, and this mode reads the site. ' +
                 'See group_connected, which is observable without administrative rights.')

    # Classified at all: a label, or a classification string, or both. False
    # only when both loaded and both were empty.
    if ($label.ok -and $class.ok) {
        $facts.classification['classified'] = New-ScalarFact `
            -Value ($null -ne $label.value -or $null -ne $class.value) `
            -RawField 'SensitivityLabelInfo.Id or Classification'
    }
    elseif (($label.ok -and $label.value) -or ($class.ok -and $class.value)) {
        # One of the two is set, so the site is classified whatever the other says.
        $facts.classification['classified'] = New-ScalarFact -Value $true `
            -RawField 'SensitivityLabelInfo.Id or Classification'
    }
    else {
        $unread = if ($label.ok) { $class.state } else { $label.state }
        $facts.classification['classified'] = New-AbsentFact -State $unread `
            -Detail 'Neither the label nor the classification could be read, so whether this site is classified is not known.'
    }
    return $facts
}

Export-ModuleMember -Function Get-ClassificationFacts
