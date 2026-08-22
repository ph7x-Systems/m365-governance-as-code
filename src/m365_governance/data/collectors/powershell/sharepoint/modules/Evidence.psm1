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
$script:IdentityKind = 'delegated'
$script:IdentityMethod = 'interactive'
$script:ClientId = $null

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
        [Parameter(Mandatory = $true)] [string] $TenantHost,
        # WHO COLLECTED THIS, and it was hard-coded to `delegated`. A run that
        # authenticated the APPLICATION with a certificate produced evidence
        # that described itself as one person's view, which is the difference
        # between a partial audit and a misleading one -- the exact sentence
        # already in the provenance comment, made untrue by the field beside
        # it the day app-only became possible.
        [Parameter()] [ValidateSet('delegated', 'application')] [string] $IdentityKind = 'delegated',
        # HOW it authenticated, which is a different question from what kind of
        # identity it is. Kept apart because only the kind changes what an
        # empty result means; the method is operational provenance.
        [Parameter()] [ValidateSet('interactive', 'device-code', 'certificate')] [string] $IdentityMethod = 'interactive',
        # The application the run authenticated as. Never the certificate,
        # never the key, never the token: a client id names a registration an
        # administrator can look up, and the rest is a credential.
        [Parameter()] [string] $ClientId
    )
    $script:CollectorName = $CollectorName
    $script:CollectorVersion = $CollectorVersion
    $script:TenantHost = $TenantHost
    $script:IdentityKind = $IdentityKind
    $script:IdentityMethod = $IdentityMethod
    $script:ClientId = $ClientId
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
    <#
        .SYNOPSIS
        Which tenant this document is about, and how that was established.

        .DESCRIPTION
        THE HOST IS WHAT WAS ASKED FOR. It is derived from the address the
        caller gave, normalised, and verified by nothing: no step in a
        collection reads the directory the session is actually operating in.
        With `id` null, that makes the requested address the identity of the
        tenant an assessment is about, which is a stronger claim than anything
        here can support.

        SO IT SAYS WHICH IT IS. `how` carries the same distinction `connection`
        already draws between a lookup anybody can perform and something a
        session observed. Nothing here may say `observed` until a collection
        path for the directory identity is proven on a tenant; the candidate is
        recorded in docs/COLLECTION-PATH-AUDIT.md as needs-tenant-validation.
    #>
    [ordered]@{
        # Null until a collection path for the directory identity is proven on
        # a tenant. The host is an endpoint, and saying so is the point.
        id   = $null
        host = $script:TenantHost
        how  = 'requested'
    }
}

function New-Evidence {
    param(
        $Resource,
        $Facts,
        [string[]] $Requested,
        [string[]] $Completed,
        $Unavailable,
        [string] $SourceApi = 'PnP.PowerShell / CSOM',
        # WHICH MICROSOFT 365 SERVICE THIS DOCUMENT IS ABOUT. It was hardcoded
        # to SharePoint Online, and the first licensing document said so while
        # describing a directory read: `source_api` said Microsoft Graph and
        # `source_system` said SharePoint Online, in the same provenance block,
        # about the same bytes.
        #
        # ONE VALUE FOR A DOCUMENT THAT READ MORE THAN ONE SURFACE IS A REAL
        # LIMIT OF THIS FIELD. The licensing document reads the directory and
        # the Microsoft 365 usage reports; calling the whole of it `Microsoft
        # Entra ID` would be as narrow as calling it SharePoint Online was
        # wrong. It says `Microsoft 365` until provenance can be carried per
        # acquisition attempt, which is where the exact surface belongs and
        # where `acquisition_attempts` already records the operation.
        [string] $SourceSystem = 'SharePoint Online'
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
        '$schema'      = 'https://ph7x.com/schemas/m365-governance/evidence/3.1.0'
        provenance     = [ordered]@{
            collected_at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            collector         = $script:CollectorName
            collector_version = $script:CollectorVersion
            source_system     = $SourceSystem
            source_api        = $SourceApi
            # A tenant has one identity and any number of addresses, and the
            # block that says which is built in ONE place. It was built here as
            # well, inline, which is the duplication the note above
            # New-TenantIdentity warns about: the two disagreed the moment one
            # of them learned to say how the identity was established.
            tenant            = New-TenantIdentity
            # Interactive and device sign-in are both delegated; a
            # certificate authenticates the application. Recording it is the
            # difference between a partial audit and a misleading one.
            identity_kind     = $script:IdentityKind
            identity_method   = $script:IdentityMethod
            client_id         = $script:ClientId
            # How it got here, which is a different question from who read it.
            acquisition       = 'collected'
            scopes            = @('AllSites.Read')
        }
        coverage       = [ordered]@{
            requested   = $Requested
            completed   = $Completed
            # A KEY WITH NO ENTRY IS NOT AN ABSENT KEY. A collector builds this
            # table with one branch per area and assigns `$null` to the areas
            # that completed; PowerShell keeps the key, `ConvertTo-Json` writes
            # `"usage": null`, and the first consumer to read `unavailable`
            # crashes on a member of `$null`. That happened on the first live
            # licensing run: the collection succeeded, the usage report was
            # read, and `stats` could not open the document it produced.
            #
            # Pruned HERE and not in each collector, because every collector
            # builds this the same way and the contract is the same for all of
            # them: an area is either unavailable with a reason, or it is not in
            # this table.
            unavailable = $(
                $kept = [ordered]@{}
                if ($null -ne $Unavailable) {
                    foreach ($area in $Unavailable.Keys) {
                        if ($null -ne $Unavailable[$area]) { $kept[$area] = $Unavailable[$area] }
                    }
                }
                $kept
            )
        }
        resource       = $Resource
        facts          = $Facts
    }
}

function Write-Evidence {
    param(
        $Evidence,
        # THE DIRECTORY THE EVIDENCE GOES INTO. Always. `collect --output` names
        # a directory and this is where that promise is kept.
        [string] $Path,
        # The document's name, without extension, for a caller that writes many
        # documents and needs to control which is which. Omitted, the name is
        # derived from the resource being described.
        [string] $Name
    )

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
    # `-Path` IS A DIRECTORY. Not sometimes, and never decided by looking at
    # the string: `collect --output` names a directory, so every layer beneath
    # it names a directory, and the writer names the document.
    #
    # IT USED TO MEAN BOTH. A mode writing many documents joined a file name
    # onto it; a mode writing one passed it straight through, so `--output
    # ./evidence/licensing/` produced a FILE called `licensing` and the caller
    # then failed creating the directory of that name. The collection had
    # succeeded -- a tenant was read, the evidence was written -- and the run
    # reported failure because of where the bytes landed. A caller that needs
    # to choose the name passes `-Name`; nobody infers anything from `.json`.
    $document = $Name
    if (-not $document) {
        $resource = $Evidence.resource
        foreach ($k in @('url', 'native_id', 'display_name')) {
            if ($resource.Contains($k) -and -not [string]::IsNullOrWhiteSpace($resource[$k])) {
                $document = $resource[$k]
                break
            }
        }
        if (-not $document) { $document = "$($resource['workload'])-$($resource['type'])" }
    }
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path | Out-Null }
    $file = Join-Path $Path ((Get-SafeName $document) + '.json')

    $Evidence | ConvertTo-Json -Depth 14 | Set-Content -Path $file -Encoding utf8
    Write-Host "  $file"
}

function Get-SafeName {
    param([string] $Value)
    return ($Value -replace '^https?://', '' -replace '[^A-Za-z0-9._-]', '-').Trim('-')
}

Export-ModuleMember -Function New-Unavailable, New-TenantIdentity, New-ScalarFact, New-AbsentFact, Resolve-FailureState, New-Evidence, Write-Evidence, Get-SafeName, Initialize-Evidence
