<#
    Agents.psm1

    The Copilot agents in one site collection, and the sources each was
    pointed at.

    An agent in SharePoint is a `.agent` file in the site's Site Assets
    library, which is why this is readable at all: there is no agent service
    to call. `Get-PnPCopilotAgent` returns the file's own definition, and the
    capabilities inside it name every site, library or item the author told it
    to read.

    TWO THINGS THIS DELIBERATELY DOES NOT DO.

    It does not report who may use an agent. That is the file's permissions,
    a separate read, and answering half of it here would invite the reading
    that the two halves are one: the file decides who holds the agent, and
    each user's own permissions decide what it can tell them.

    It does not report the agent's instructions. They are readable, they are
    frequently indiscreet, and copying free text somebody wrote into an
    evidence document that gets shared is a disclosure this product will not
    make on its own. The count is evidence; the prose is theirs.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'Evidence.psm1') -Force

function Get-AgentSourceList {
    <#
        The sources one agent declares, from both shapes the file uses:
        `ItemsByUrl` for things named by address and `ItemsBySharePointIds`
        for things named by identifier. Either way the agent is saying what it
        was told to read.
    #>
    param($Definition)

    $sources = @()
    foreach ($capability in @($Definition.Capabilities)) {
        if (-not $capability) { continue }
        foreach ($group in @('ItemsByUrl', 'ItemsBySharePointIds')) {
            foreach ($item in @($capability.$group)) {
                if (-not $item) { continue }
                $sources += [ordered]@{
                    url       = [string] $item.Url
                    name      = [string] $item.Name
                    type      = [string] $item.Type
                    site_id   = [string] $item.SiteId
                    web_id    = [string] $item.WebId
                    list_id   = [string] $item.ListId
                    unique_id = [string] $item.UniqueId
                    named_by  = if ($group -eq 'ItemsByUrl') { 'url' } else { 'id' }
                }
            }
        }
    }
    return , $sources
}

function Get-AgentFacts {
    <#
        Every agent this identity can see in this site collection.

        An empty result is NOT `no agents`. A site with none and a site this
        identity cannot open return the same thing, so the count travels with
        the fact that it is bounded by one identity, and the caller records
        that in coverage rather than in a footnote.
    #>
    param()

    try {
        $agents = @(Get-PnPCopilotAgent -ErrorAction Stop)
    }
    catch {
        $state = Resolve-FailureState $_
        return [ordered]@{
            agents = [ordered]@{
                inventory = New-AbsentFact -State $state -Detail $_.Exception.Message
                count     = New-AbsentFact -State $state `
                    -Detail 'The site was not read, so no count exists for it.'
            }
        }
    }

    $inventory = @()
    foreach ($agent in $agents) {
        $config = $null
        $definition = $null
        try { $config = $agent.CustomCopilotConfig } catch { $config = $null }
        if ($config) {
            try { $definition = $config.GPTDefinition } catch { $definition = $null }
        }

        $sources = if ($definition) { Get-AgentSourceList -Definition $definition } else { @() }

        # `has_instructions`, and not the instructions themselves. Knowing
        # that a prompt exists is governance; copying somebody's free text
        # into an evidence document that gets shared is disclosure.
        $hasInstructions = $false
        if ($definition -and $definition.Instructions) {
            $hasInstructions = -not [string]::IsNullOrWhiteSpace($definition.Instructions)
        }

        $inventory += [ordered]@{
            file             = [string] $agent.ServerRelativeUrl
            type             = [string] $agent.AgentType
            schema_version   = [string] $agent.SchemaVersion
            name             = if ($definition) { [string] $definition.Name } else { '' }
            description      = if ($definition) { [string] $definition.Description } else { '' }
            has_instructions = $hasInstructions
            source_count     = @($sources).Count
            sources          = $sources
        }
    }

    $facts = [ordered]@{ agents = [ordered]@{} }
    $facts.agents['inventory'] = New-ScalarFact -Value $inventory `
        -RawField 'Get-PnPCopilotAgent'
    $facts.agents['count'] = New-ScalarFact -Value (@($inventory).Count) `
        -RawField 'Get-PnPCopilotAgent'

    # Derived from what was observed: how many sources the agents on this
    # site declare between them. It does not say who can reach any of them,
    # which is the other read entirely.
    $totalSources = 0
    foreach ($a in $inventory) { $totalSources += [int] $a.source_count }
    $facts.agents['source_count'] = New-ScalarFact -Value $totalSources `
        -RawField 'Get-PnPCopilotAgent'

    # An agent with no declared source answers from the site it lives in and
    # from nothing else. That is an observation rather than a defect, and a
    # report that omits it stops distinguishing the two cases.
    $withoutSources = @($inventory | Where-Object { $_.source_count -eq 0 }).Count
    $facts.agents['agents_without_declared_sources'] =
        New-ScalarFact -Value $withoutSources -RawField 'Get-PnPCopilotAgent'

    return $facts
}

Export-ModuleMember -Function Get-AgentFacts, Get-AgentSourceList
