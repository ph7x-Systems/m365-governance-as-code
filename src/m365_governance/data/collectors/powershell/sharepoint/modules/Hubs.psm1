Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

<#
    Hub sites: which sites the organisation has made hubs, and how each is set.

    AN INVENTORY WITH A NAMED READER AND NO RULE. Microsoft documents what a
    hub is and how to plan one, and publishes no position on how many an
    organisation should have or how each should be set, so a threshold would be
    invented. The reader is the operator enumerating hubs and the report.

    Source: Get-PnPHubSite, which returns the tenant's HubSiteProperties.
    Checked against PnP.PowerShell 3.4.1 on 11 November 2026.

    WHAT IS NOT READ. Which sites are associated with a hub is a property of
    each associated site and is not carried by the hub; the logo, the site
    design and the description are presentation and feed nothing.
#>

function Get-HubPopulationFacts {
    param([Parameter(Mandatory = $true)] [int] $Count)

    [ordered]@{
        hubs = [ordered]@{
            population         = New-ScalarFact -Value 'sharepoint-registered-hub-sites' `
                -RawField 'Get-PnPHubSite'
            acquisition_method = New-ScalarFact -Value 'enumerated' -RawField 'Get-PnPHubSite'
            count              = New-ScalarFact -Value $Count -RawField 'Get-PnPHubSite | Measure-Object'
        }
    }
}

function Get-HubFacts {
    param([Parameter(Mandatory = $true)] $Hub)

    $empty = [guid]::Empty
    $facts = [ordered]@{ hub = [ordered]@{} }

    $scalars = [ordered]@{
        hub_site_id               = 'ID'
        site_id                   = 'SiteId'
        requires_join_approval    = 'RequiresJoinApproval'
        permissions_sync_enabled  = 'EnablePermissionsSync'
        name_hidden_in_navigation = 'HideNameInNavigation'
    }
    foreach ($name in $scalars.Keys) {
        $property = $scalars[$name]
        try {
            $value = $Hub.$property
            if ($null -eq $value) {
                $facts.hub[$name] = New-AbsentFact -State 'missing' `
                    -Detail "$property was not returned for this hub."
            }
            elseif ($value -is [guid]) {
                $facts.hub[$name] = New-ScalarFact -Value ([string] $value) -RawField $property
            }
            else {
                $facts.hub[$name] = New-ScalarFact -Value $value -RawField $property
            }
        }
        catch {
            $facts.hub[$name] = New-AbsentFact -State (Resolve-FailureState $_) `
                -Detail $_.Exception.Message
        }
    }

    # A PARENT IS A HUB THIS ONE IS ASSOCIATED WITH. SharePoint writes the
    # empty identifier when there is none, and that is an answer: reported as
    # a boolean so that nobody has to know what an all-zero GUID means.
    try {
        $parent = $Hub.ParentHubSiteId
        $has = ($null -ne $parent) -and ([guid] $parent -ne $empty)
        $facts.hub.has_parent_hub = New-ScalarFact -Value $has -RawField 'ParentHubSiteId'
        if ($has) {
            $facts.hub.parent_hub_site_id = New-ScalarFact -Value ([string] $parent) `
                -RawField 'ParentHubSiteId'
        }
    }
    catch {
        $facts.hub.has_parent_hub = New-AbsentFact -State (Resolve-FailureState $_) `
            -Detail $_.Exception.Message
    }

    # WHO MAY ASSOCIATE A SITE WITH THIS HUB. An empty list is the documented
    # default and means nobody is restricted. The principals are not
    # published: the count is the fact, and a name is a person.
    try {
        $principals = @($Hub.Permissions)
        $facts.hub.association_restricted = New-ScalarFact `
            -Value ($principals.Count -gt 0) -RawField 'Permissions'
        $facts.hub.association_principals = New-ScalarFact `
            -Value $principals.Count -RawField 'Permissions | Measure-Object'
    }
    catch {
        $facts.hub.association_restricted = New-AbsentFact `
            -State (Resolve-FailureState $_) -Detail $_.Exception.Message
    }

    return $facts
}

Export-ModuleMember -Function Get-HubFacts, Get-HubPopulationFacts
