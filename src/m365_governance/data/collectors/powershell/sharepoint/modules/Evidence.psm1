<#
    Evidence.psm1

    The shape of every fact this collector emits, and nothing that reads a
    tenant. It is the bottom of the stack: it imports nothing, and a cycle
    through it would be a design error rather than an inconvenience.

    `Initialize-Evidence` exists because provenance used to be read from
    script-scope variables. A module has its own session state, so those reads
    would have found nothing here; passing them in makes the dependency
    visible instead of ambient.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Module scope, set once by Initialize-Evidence. Not read from the caller:
# that is precisely the ambient dependency this module was split to remove.
$script:CollectorName = $null
$script:CollectorVersion = $null
$script:TenantHost = $null

function Initialize-Evidence {
    <#
        .SYNOPSIS
        Records who is collecting, and from where, for every later envelope.

        .DESCRIPTION
        Must be called before New-Evidence. Calling New-Evidence first is a
        programming error rather than a collection failure, and it throws
        saying so instead of writing a document with a null provenance.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string] $CollectorName,
        [Parameter(Mandatory = $true)] [string] $CollectorVersion,
        [Parameter(Mandatory = $true)] [string] $TenantHost
    )
    $script:CollectorName = $CollectorName
    $script:CollectorVersion = $CollectorVersion
    $script:TenantHost = $TenantHost
}

function New-Unavailable {
    param([string] $State, [string] $Detail)
    return [ordered]@{ state = $State; detail = $Detail }
}

function New-ScalarFact {
    param($Value, [string] $RawField)
    return [ordered]@{
        state = 'observed'
        value = $Value
        raw   = [ordered]@{ field = $RawField; value = $Value }
    }
}

function New-AbsentFact {
    param([string] $State, [string] $Detail)
    return [ordered]@{ state = $State; detail = $Detail }
}

function Resolve-FailureState {
    <#
        Maps an exception onto a collection state. permission-denied is kept
        separate from missing because it is the only one whose fix is a human
        decision about access, and the one most often laundered into
        "no data, therefore fine".
    #>
    param([System.Management.Automation.ErrorRecord] $ErrorRecord)

    $message = $ErrorRecord.Exception.Message
    if ($message -match 'Access denied|Unauthorized|403|does not have permission') {
        return 'permission-denied'
    }
    if ($message -match 'not found|404|does not exist') { return 'missing' }
    if ($message -match 'not supported|NotImplemented') { return 'not-supported' }
    return 'missing'
}

<#
    The tenant a resource belongs to, in one place.

    Identity is structured now, so every resource carries its own tenant rather
    than borrowing it from the document it happens to sit in. Written once here
    because twelve call sites building the same hashtable is twelve chances for
    one of them to differ.
#>
function New-TenantIdentity {
    [ordered]@{
        # Null until a collection path for the directory identity is proven on
        # a tenant. The host is an endpoint, and saying so is the point.
        id   = $null
        host = $script:TenantHost
    }
}

function New-Evidence {
    param(
        $Resource,
        $Facts,
        [string[]] $Requested,
        [string[]] $Completed,
        $Unavailable,
        [string] $SourceApi = 'PnP.PowerShell / CSOM'
    )
    if (-not $script:CollectorName) {
        throw 'Initialize-Evidence was not called: an envelope has no provenance.'
    }
    return [ordered]@{
        # The exact contract this document claims. Inside a schema document
        # `$schema` names the JSON Schema dialect; inside an instance it is an
        # ordinary property, and this is where the two conventions are kept
        # apart. It replaces `schema_version = '1.0'`, a second version that
        # could not express the one in the schema's own $id.
        '$schema'      = 'https://ph7x.com/schemas/m365-governance/evidence/3.0.0'
        provenance     = [ordered]@{
            collected_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            collector         = $script:CollectorName
            collector_version = $script:CollectorVersion
            source_system     = 'SharePoint Online'
            source_api        = $SourceApi
            # A tenant has one identity and any number of addresses. The
            # directory id is the identity and nothing here has read one yet,
            # so it is null and says so: an omitted field would claim nothing
            # was ever meant to be there. The host is an endpoint, already
            # normalised so the admin centre and a site agree.
            tenant            = [ordered]@{ id = $null; host = $script:TenantHost }
            # Interactive and device sign-in are both delegated. Recording it
            # is the difference between a partial audit and a misleading one.
            identity_kind     = 'delegated'
            # How it got here, which is a different question from who read it.
            acquisition       = 'collected'
            scopes            = @('AllSites.Read')
        }
        coverage       = [ordered]@{
            requested   = $Requested
            completed   = $Completed
            unavailable = $Unavailable
        }
        resource       = $Resource
        facts          = $Facts
    }
}

function Write-Evidence {
    param($Evidence, [string] $Path)

    # An optional field that could not be read is not written as null. The
    # schema rejects null, and it is right to: "not known" has its own state on
    # a fact, and on a descriptive field the absence of the key says the same
    # thing without inventing a value.
    foreach ($k in @('display_name', 'url')) {
        if ($Evidence.resource.Contains($k) -and
            [string]::IsNullOrWhiteSpace($Evidence.resource[$k])) {
            $Evidence.resource.Remove($k)
        }
    }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    $Evidence | ConvertTo-Json -Depth 14 | Set-Content -Path $Path -Encoding utf8
    Write-Host "  $Path"
}

function Get-SafeName {
    param([string] $Value)
    return ($Value -replace '^https?://', '' -replace '[^A-Za-z0-9._-]', '-').Trim('-')
}

Export-ModuleMember -Function New-Unavailable, New-TenantIdentity, New-ScalarFact, New-AbsentFact, Resolve-FailureState, New-Evidence, Write-Evidence, Get-SafeName, Initialize-Evidence
