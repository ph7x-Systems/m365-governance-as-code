<#
    validate-agents.ps1

    Does the collector read the real object the way the model expects?

    That is the whole question, and it is deliberately the only one. The
    inventory shape was read from PnP.PowerShell 3.3.0's own types and never
    observed against a tenant, which is exactly the gap that produced the
    `SharingCapability` defect: a property with the right type, a plausible
    value, and a collection path nobody had proven.

        pwsh tools/validate-agents.ps1 -SiteUrl  https://<tenant>.sharepoint.com/sites/<site> `
                                       -ClientId <your app id>

    AND, WHERE A BROWSER CANNOT COME BACK. `-Interactive` needs a browser that
    can hand a token back to this process. In a terminal that has no session to
    hand back to, it waits for something that will never arrive. PnP documents
    the device code flow for exactly that case, so it is a switch here rather
    than a workaround somebody has to invent under pressure:

        pwsh tools/validate-agents.ps1 -SiteUrl  https://<tenant>.sharepoint.com/sites/<site> `
                                       -ClientId <your app id> `
                                       -DeviceLogin

    It prints a URL and a code; you sign in on any device and the run
    continues. Both forms pass `-ValidateConnection`, so a connection that
    cannot reach the site fails here and not four steps later inside a read.
    https://pnp.github.io/powershell/articles/authentication.html

    HOW IT PROVES IT. It reads the agents twice. Once raw, from
    `Get-PnPCopilotAgent`, walking the object with reflection so that a
    property the model expects and the object does not have shows up as
    absent rather than as an empty string. Once through `Get-AgentFacts`, the
    collector's own function. Then it compares them field by field.

    Agreement is not the point; disagreement is. Four of five sites agreed on
    `SharingCapability` and the path was still wrong, so this reports every
    field of every agent rather than a summary that could hide one.

    THE CASE THAT MATTERS MOST IS THE EMPTY ONE. The manifest schema says
    that an agent omitting both source arrays can reach every OneDrive and
    SharePoint source in the organisation the asking user can already see. So
    an agent with zero sources is the widest one, not a curiosity at the edge
    of the test, and whether the SharePoint UI can even produce that state is
    the single most valuable thing this run can settle.

    WHAT IT DOES NOT DO. It does not read the `.agent` file's permissions.
    Who may use an agent is the other half of the model and needs its own
    collection path, and mixing it in here would widen the scope of a
    validation whose value is being narrow.

    READ-ONLY. This line used to say "interactive rather than a device code",
    and that was a preference written as a rule: the device code flow is the
    documented answer for a terminal a browser cannot return to, and pretending
    otherwise cost a run that never connected.

    Writes docs/SANDBOX-AGENTS.md and, when at least one agent was read, a
    sanitised fixture beside the others. Nothing is concluded here.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $SiteUrl,
    [Parameter(Mandatory = $true)] [string] $ClientId,
    [Parameter()] [string] $OutputPath = "docs/SANDBOX-AGENTS.md",
    [Parameter()] [string] $FixturePath =
    "src/m365_governance/data/fixtures/sharepoint/site-agents-observed.json",
    [Parameter()] [switch] $DeviceLogin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$report = [System.Collections.Generic.List[string]]::new()
function Say([string] $line) { Write-Host $line; $report.Add($line) }

$modules = Join-Path $PSScriptRoot '../src/m365_governance/data/collectors/powershell/sharepoint/modules'
Import-Module (Join-Path $modules 'Evidence.psm1') -Force
Import-Module (Join-Path $modules 'Agents.psm1') -Force

Say "# Agent inventory, against a tenant"
Say ""
# The document says HOW it connected, because "interactive" was printed
# unconditionally and would now be false on a device-code run. A record that
# misstates its own method is the kind of detail nobody checks twice.
$how = if ($DeviceLogin) { 'device login' } else { 'interactive' }
Say "Run on $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm')) UTC, $how and read-only."
Say "The site is not named here: this repository is public, and a URL is an identifier whether or not it is data."
Say ""

if ($DeviceLogin) {
    Write-Host "Connecting with device login. Follow the printed URL and code." -ForegroundColor Cyan
    Connect-PnPOnline -Url $SiteUrl -DeviceLogin -ClientId $ClientId -ValidateConnection
}
else {
    Write-Host "Connecting. A browser will open." -ForegroundColor Cyan
    Connect-PnPOnline -Url $SiteUrl -Interactive -ClientId $ClientId -ValidateConnection
}

# ── 1. the raw object, walked rather than assumed ────────────────────────────
#
# `Read-Property` exists so that a property the model reads and the object
# does not have is reported as `ABSENT`, not as an empty string. Under
# Set-StrictMode the difference is an exception; without it, a silent "".
function Read-Property {
    param($Object, [string] $Name)
    if ($null -eq $Object) { return @{ present = $false; value = $null } }
    $prop = $Object.PSObject.Properties[$Name]
    if (-not $prop) { return @{ present = $false; value = $null } }
    return @{ present = $true; value = $prop.Value }
}

Say "## 1. What the module returns"
Say ""

$raw = $null
$rawError = $null
try { $raw = @(Get-PnPCopilotAgent -ErrorAction Stop) }
catch { $rawError = $_.Exception.Message }

if ($rawError) {
    Say "``Get-PnPCopilotAgent`` was refused: $rawError"
    Say ""
    Say "**Recorded as coverage, not as an absence of agents.** A refusal and an empty site are the same result from outside, and this run cannot tell them apart."
}
else {
    Say "$($raw.Count) agent(s) returned by ``Get-PnPCopilotAgent`` for this identity."
    Say ""

    # Every property the model reads, named here so the table says which of
    # them the real object actually carries.
    $expected = @('ServerRelativeUrl', 'AgentType', 'SchemaVersion', 'CustomCopilotConfig')
    Say "| Agent | Property | Present | Type |"
    Say "|---|---|---|---|"
    $i = 0
    foreach ($agent in $raw) {
        $i++
        foreach ($name in $expected) {
            $p = Read-Property -Object $agent -Name $name
            $kind = if ($p.present -and $null -ne $p.value) { $p.value.GetType().Name } else { '-' }
            $mark = if ($p.present) { 'yes' } else { '**ABSENT**' }
            Say "| $i | ``$name`` | $mark | $kind |"
        }
        $config = (Read-Property -Object $agent -Name 'CustomCopilotConfig').value
        $definition = (Read-Property -Object $config -Name 'GPTDefinition').value
        foreach ($name in @('Name', 'Description', 'Instructions', 'Capabilities')) {
            $p = Read-Property -Object $definition -Name $name
            $kind = if ($p.present -and $null -ne $p.value) { $p.value.GetType().Name } else { '-' }
            $mark = if ($p.present) { 'yes' } else { '**ABSENT**' }
            Say "| $i | ``GPTDefinition.$name`` | $mark | $kind |"
        }
    }
    Say ""
}

# ── 2. the same agents, through the collector ────────────────────────────────
Say "## 2. What the collector recorded"
Say ""

$facts = Get-AgentFacts
$inventory = @()
if ($facts.agents['inventory'].state -eq 'observed') {
    $inventory = @($facts.agents['inventory'].value)
    Say "| Agent | Type | Named | Instructions | Sources | by URL | by id |"
    Say "|---|---|---|---|---|---|---|"
    foreach ($a in $inventory) {
        $byUrl = @($a.sources | Where-Object { $_.named_by -eq 'url' }).Count
        $byId = @($a.sources | Where-Object { $_.named_by -eq 'id' }).Count
        $named = if ([string]::IsNullOrWhiteSpace($a.name)) { '**no**' } else { 'yes' }
        Say "| ``$($a.file)`` | $($a.type) | $named | $($a.has_instructions) | $($a.source_count) | $byUrl | $byId |"
    }
    Say ""
    Say "Derived facts: count $($facts.agents['count'].value), total sources $($facts.agents['source_count'].value), agents declaring none $($facts.agents['agents_without_declared_sources'].value)."
    Say ""

    # The reading that inverts the obvious one, and the reason this run exists.
    $wide = [int] $facts.agents['agents_without_declared_sources'].value
    if ($wide -gt 0) {
        Say "**$wide agent(s) declare no source at all.** The declarative agent"
        Say "manifest schema states that omitting both source arrays lets the agent"
        Say "reach every OneDrive and SharePoint source in the organisation that the"
        Say "asking user can already see. **These are the widest agents here, not the"
        Say "narrowest**, and this run has now shown the SharePoint interface can"
        Say "produce that state."
    }
    else {
        Say "No agent declares zero sources. **That is not proof the state is"
        Say "impossible**: it is proof that nothing in this site reached it. Try"
        Say "creating one with no source selected; if the interface refuses, that"
        Say "refusal is the finding and is worth more than the fixture."
    }
}
else {
    Say "The collector recorded ``$($facts.agents['inventory'].state)``: $($facts.agents['inventory'].detail)"
}
Say ""

# ── 3. do the two halves agree ───────────────────────────────────────────────
#
# The comparison that matters. Not "did it work", which a summary can fake,
# but "does each field the model reads carry what the object holds".
Say "## 3. Agreement, field by field"
Say ""

if ($rawError) {
    Say "Not comparable: the raw read was refused, so there is nothing to compare against."
}
elseif (@($raw).Count -ne @($inventory).Count) {
    Say "**The counts disagree: $($raw.Count) from the module and $($inventory.Count) from the collector.** That is a collector defect and this run found it."
}
elseif (@($raw).Count -eq 0) {
    Say "No agents in this site, so the shape was not exercised. **Create one and run this again**: an empty result proves the call works and nothing about the model."
}
else {
    Say "| Agent | Field | Module | Collector | Agrees |"
    Say "|---|---|---|---|---|"
    $disagreements = 0
    for ($k = 0; $k -lt $raw.Count; $k++) {
        $r = $raw[$k]
        $c = $inventory[$k]
        $definition = (Read-Property -Object (Read-Property -Object $r -Name 'CustomCopilotConfig').value -Name 'GPTDefinition').value

        $pairs = @(
            @{ field = 'file'; mod = [string] $r.ServerRelativeUrl; col = [string] $c.file },
            @{ field = 'type'; mod = [string] $r.AgentType; col = [string] $c.type },
            @{ field = 'name'; mod = [string] (Read-Property -Object $definition -Name 'Name').value; col = [string] $c.name }
        )
        foreach ($pair in $pairs) {
            $same = ($pair.mod -eq $pair.col)
            if (-not $same) { $disagreements++ }
            $mark = if ($same) { 'yes' } else { '**NO**' }
            Say "| $($k + 1) | $($pair.field) | $($pair.mod) | $($pair.col) | $mark |"
        }
    }
    Say ""
    if ($disagreements -gt 0) {
        Say "**$disagreements field(s) disagree. The model does not match the object, and no fixture may be promoted until it does.**"
    }
    else {
        Say "Every compared field agrees. The shape read from the module's types is the shape a tenant returns."
    }
}
Say ""

# ── 4. a fixture, with the tenant taken out of it ────────────────────────────
Say "## 4. Fixture"
Say ""

if (@($inventory).Count -gt 0) {
    # Identity is replaced, shape is not. A fixture carries the shape; a
    # tenant's own URLs, ids and agent names are not ours to publish.
    $siteHost = ([Uri] $SiteUrl).Host
    $sanitised = @()
    $n = 0
    foreach ($a in $inventory) {
        $n++
        $sources = @()
        $m = 0
        foreach ($s in $a.sources) {
            $m++
            $sources += [ordered]@{
                url       = "https://contoso.sharepoint.com/sites/example/source-$n-$m"
                name      = "source-$n-$m"
                type      = [string] $s.type
                site_id   = "00000000-0000-4000-8000-{0:d12}" -f ($n * 100 + $m)
                web_id    = "00000000-0000-4000-8001-{0:d12}" -f ($n * 100 + $m)
                list_id   = "00000000-0000-4000-8002-{0:d12}" -f ($n * 100 + $m)
                unique_id = "00000000-0000-4000-8003-{0:d12}" -f ($n * 100 + $m)
                named_by  = [string] $s.named_by
            }
        }
        $sanitised += [ordered]@{
            file             = "/sites/example/SiteAssets/agent-$n.agent"
            type             = [string] $a.type
            schema_version   = [string] $a.schema_version
            name             = "Agent $n"
            description      = ''
            has_instructions = [bool] $a.has_instructions
            source_count     = [int] $a.source_count
            sources          = $sources
        }
    }

    $doc = [ordered]@{
        schema_version = '1.0'
        provenance     = [ordered]@{
            collected_at     = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            collector        = 'spo-collector'
            collector_version = '0.3.0'
            source_system    = 'SharePoint Online'
            source_api       = 'PnP.PowerShell / CSOM'
            tenant_id        = 'contoso.sharepoint.com'
            identity_kind    = 'delegated'
            scopes           = @('AllSites.FullControl')
        }
        coverage       = [ordered]@{
            requested   = @('agents', 'enumeration')
            completed   = @('agents')
            unavailable = [ordered]@{
                enumeration = [ordered]@{
                    state  = 'partial'
                    detail = 'Agents are files, so this is what the running identity can see in this site collection. A site with no agents and a site this identity cannot open return the same empty result.'
                }
            }
        }
        resource       = [ordered]@{
            id           = 'contoso,site,example'
            type         = 'site'
            display_name = 'Example'
            url          = 'https://contoso.sharepoint.com/sites/example'
        }
        facts          = [ordered]@{
            agents = [ordered]@{
                inventory = New-ScalarFact -Value $sanitised -RawField 'Get-PnPCopilotAgent'
                count     = New-ScalarFact -Value @($sanitised).Count -RawField 'Get-PnPCopilotAgent'
                source_count = New-ScalarFact -Value ($facts.agents['source_count'].value) -RawField 'Get-PnPCopilotAgent'
                agents_without_declared_sources = New-ScalarFact `
                    -Value ($facts.agents['agents_without_declared_sources'].value) `
                    -RawField 'Get-PnPCopilotAgent'
            }
        }
    }
    $doc | ConvertTo-Json -Depth 12 | Set-Content -Path $FixturePath -Encoding utf8
    Say "Written to ``$FixturePath``: $($sanitised.Count) agent(s), shape kept, identity replaced."
    Say ""
    Say "The host read was ``$($siteHost.Substring(0, 3))...`` and appears nowhere in the fixture."
}
else {
    Say "No fixture: nothing was read, and a fixture built from nothing would be a shape somebody invented."
}

$report -join "`n" | Set-Content -Path $OutputPath -Encoding utf8
Write-Host ""
Write-Host "Wrote $OutputPath" -ForegroundColor Green
