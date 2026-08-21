<#
    Get-LicensingEvidence.ps1

    WHAT IS ASSIGNED, AND WHETHER ITS USE CAN BE OBSERVED.

    This orchestrates and does not collect: connect, read, call one function,
    emit JSON. The reads live in `modules/Licensing.psm1` and the shape of the
    evidence is decided there.

    IT IS A DIFFERENT ACQUISITION SURFACE FROM EVERY OTHER COLLECTOR HERE.
    Every module under `collectors/powershell/sharepoint` reads SharePoint
    through PnP. This reads the directory and the reporting endpoints through
    Microsoft Graph, under different permissions, with a different sign-in, and
    with one property the others have no equivalent of: whether the reports are
    allowed to name anybody.

    WHAT IT REFUSES TO DO. It produces no conclusion about changing an
    assignment. That needs evidence of use AND of dependency; this reads the
    first at best, and the second not at all. `dependency_evidence` is recorded
    as absent by construction so that a usage figure cannot be read as an answer.

    THE PREREQUISITE IS EVIDENCE, NOT A CRASH. The Microsoft Graph PowerShell
    modules are a large install and are frequently absent. A collector that
    threw on the import would be indistinguishable, to a caller, from a tenant
    that returned nothing. It reports `not-supported` with the module name
    instead, which is a fact about this machine and says nothing about the
    tenant.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Connect', 'Licensing')]
    [string] $Mode,

    [Parameter()]
    [string] $OutputPath,

    [Parameter()]
    [string] $TenantHost,

    # The reporting period, passed through to Graph unchanged. The four values
    # Microsoft supports, and no default invented here: a caller that does not
    # say which period it wants gets none read, and the evidence says so.
    [Parameter()]
    [ValidateSet('D7', 'D30', 'D90', 'D180')]
    [string] $Period,

    [Parameter()]
    [string] $ClientId,

    [Parameter()]
    [string] $TenantId,

    [Parameter()]
    [string] $CertificateThumbprint,

    [Parameter()]
    [switch] $DeviceLogin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Modules = Join-Path $PSScriptRoot 'modules'
Import-Module (Join-Path $Modules 'Licensing.psm1') -Force

# `Evidence.psm1` is the SharePoint collector's, and it is the evidence
# contract's rather than that collector's: one writer, one shape, one place the
# provenance block is decided. Reaching for it across the folder is deliberate
# and is why it is not duplicated here.
$Shared = Join-Path (Split-Path $PSScriptRoot -Parent) 'sharepoint/modules'
Import-Module (Join-Path $Shared 'Evidence.psm1') -Force

#: The modules this collector needs, named so that their absence is reportable.
$script:Required = @(
    'Microsoft.Graph.Identity.DirectoryManagement',
    'Microsoft.Graph.Users',
    'Microsoft.Graph.Reports'
)

function Test-GraphAvailable {
    $missing = @($script:Required | Where-Object {
            -not (Get-Module -ListAvailable -Name $_)
        })
    return , $missing
}

function Connect-Directory {
    param([string] $Tenant, [string] $App, [string] $Thumbprint, [switch] $Device)

    # LEAST PRIVILEGE, AND STATED. `Reports.Read.All` is what Microsoft
    # documents as the least privileged permission for the usage reports;
    # `Organization.Read.All` and `User.Read.All` are the directory half.
    $scopes = @('Organization.Read.All', 'User.Read.All', 'Reports.Read.All',
        'ReportSettings.Read.All')

    if ($Thumbprint) {
        Connect-MgGraph -TenantId $Tenant -ClientId $App `
            -CertificateThumbprint $Thumbprint -NoWelcome
    }
    elseif ($Device) {
        Connect-MgGraph -Scopes $scopes -UseDeviceCode -NoWelcome
    }
    else {
        Connect-MgGraph -Scopes $scopes -NoWelcome
    }
}

# --- the run -----------------------------------------------------------------

# WHO IS COLLECTING, BEFORE ANYTHING IS WRITTEN. `Initialize-Evidence` refuses
# to let an envelope exist without provenance, which is why it is called before
# the prerequisite check: the document written when the modules are missing is
# still a document somebody will read, and it has to say who produced it.
#
# The identity is `application` when a certificate thumbprint was supplied and
# `delegated` otherwise, and it is never assumed: a run that authenticated the
# application while describing itself as one person's view is the difference
# between a partial reading and a misleading one.
$identityKind = if ($CertificateThumbprint) { 'application' } else { 'delegated' }
$identityMethod = if ($CertificateThumbprint) { 'certificate' }
elseif ($DeviceLogin) { 'device-code' } else { 'interactive' }

Initialize-Evidence -CollectorName 'm365-licensing-collector' `
    -CollectorVersion '0.1.0' -TenantHost $TenantHost `
    -IdentityKind $identityKind -IdentityMethod $identityMethod -ClientId $ClientId

$absent = Test-GraphAvailable
if ($absent.Count -gt 0) {
    $detail = 'This version collects licensing through the Microsoft Graph ' +
    'PowerShell modules, and this machine does not have ' + ($absent -join ', ') +
    '. The limitation is this product''s, not the tenant''s: nothing about the ' +
    'tenant is established by this result.'

    # THE ATTEMPT, CLASSIFIED. `implementation` because our acquisition adapter
    # chose a prerequisite this machine does not meet. Had the directory
    # refused, or had Microsoft not exposed the endpoint in this cloud, the
    # owner would be `tenant-or-identity` or `microsoft` and the entry would be
    # evidence about the environment rather than a gap in this product.
    $attempts = @(
        foreach ($area in @('assignment', 'usage')) {
            [ordered]@{
                area       = $area
                operation  = $(if ($area -eq 'assignment') {
                        'Get-MgSubscribedSku; Get-MgUser -Property assignedLicenses'
                    }
                    else { 'adminReportSettings; reports/getOffice365ActiveUserDetail' })
                population = 'entra-licensed-user-assignments'
                identity   = $identityKind
                method     = $identityMethod
                result     = 'not-supported'
                reason     = 'required PowerShell modules absent on the collecting host'
                owner      = 'implementation'
            }
        }
    )
    if ($Mode -eq 'Connect') {
        Write-Output (@{ reach = 'refused'; because = @($detail) } | ConvertTo-Json -Depth 4)
        exit 3
    }
    # A MODE THAT CANNOT RUN STILL WRITES EVIDENCE. The alternative is a caller
    # that cannot tell "not installed here" from "nothing in the tenant", which
    # is the one confusion this whole family exists to prevent.
    Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
            -Resource ([ordered]@{
                workload = 'microsoft-365'; type = 'tenant'
                native_id = $TenantHost
                tenant = [ordered]@{ id = $null; host = $TenantHost; how = 'requested' }
                scope = 'tenant'; parent = $null
                display_name = $TenantHost; url = 'https://admin.microsoft.com'
            }) `
            -Facts (Get-LicensingFacts -SubscribedSkus $null -Assignments $null `
                -ReportSettings $null -UsageWindows $null -Attempts $attempts) `
            -Requested @('assignment', 'usage', 'dependency') -Completed @() `
            -Unavailable ([ordered]@{
                assignment = (New-Unavailable -State 'not-supported' -Detail $detail)
                usage      = (New-Unavailable -State 'not-supported' -Detail $detail)
                dependency = (New-Unavailable -State 'missing' `
                        -Detail 'Dependency evidence is not collected by this run.')
            }) `
            -SourceApi 'Microsoft Graph v1.0')
    exit 0
}

Connect-Directory -Tenant $TenantId -App $ClientId `
    -Thumbprint $CertificateThumbprint -Device:$DeviceLogin

if ($Mode -eq 'Connect') {
    $me = Get-MgContext
    Write-Output (@{
            reach   = 'established'
            because = @("Connected to $($me.TenantId) as $($me.AppName)")
        } | ConvertTo-Json -Depth 4)
    exit 0
}

# --- what is assigned --------------------------------------------------------

$skus = @(Get-MgSubscribedSku -All | ForEach-Object {
        [ordered]@{
            sku            = [string] $_.SkuPartNumber
            prepaid_units  = [int] $_.PrepaidUnits.Enabled
            consumed_units = [int] $_.ConsumedUnits
        }
    })

$assignments = @(Get-MgUser -All -Property 'id,userPrincipalName,assignedLicenses,accountEnabled' |
    Where-Object { $_.AssignedLicenses.Count -gt 0 } |
    ForEach-Object {
        [ordered]@{
            user          = [string] $_.Id
            enabled       = [bool] $_.AccountEnabled
            service_plans = @($_.AssignedLicenses.SkuId | ForEach-Object { [string] $_ })
        }
    })

# --- whether any of it can be attributed -------------------------------------
#
# FIRST, AND SEPARATELY. Everything the reports return is conditional on this
# one tenant setting, so it is read on its own and reported even when the
# reports themselves are not read.
$settings = $null
try {
    $raw = Invoke-MgGraphRequest -Method GET `
        -Uri 'https://graph.microsoft.com/beta/admin/reportSettings'
    $settings = [ordered]@{ display_concealed_names = [bool] $raw.displayConcealedNames }
}
catch {
    $settings = $null
}

# --- the usage reports, only if a period was asked for -----------------------
$windows = $null
if ($Period) {
    $windows = @()
    foreach ($report in @('getOffice365ActiveUserDetail')) {
        try {
            $null = Invoke-MgGraphRequest -Method GET -OutputFilePath ([IO.Path]::GetTempFileName()) `
                -Uri "https://graph.microsoft.com/v1.0/reports/$report(period='$Period')"
            $windows += [ordered]@{ report = $report; window_days = [int] $Period.Substring(1) }
        }
        catch {
            # A report that refused is not a report that returned nothing.
            Write-Verbose "$report refused: $($_.Exception.Message)"
        }
    }
}

$attempts = @(
    [ordered]@{
        area = 'assignment'
        operation = 'Get-MgSubscribedSku; Get-MgUser -Property assignedLicenses'
        population = 'entra-licensed-user-assignments'
        identity = $identityKind; method = $identityMethod
        result = 'observed'; reason = ''; owner = ''
    }
    [ordered]@{
        area = 'usage'
        operation = 'adminReportSettings; reports/getOffice365ActiveUserDetail'
        population = 'entra-licensed-user-assignments'
        identity = $identityKind; method = $identityMethod
        result = $(if ($windows) { 'observed' } else { 'not-collected' })
        reason = $(if ($windows) { '' } else { 'no reporting period was requested' })
        owner = $(if ($windows) { '' } else { 'caller' })
    }
    [ordered]@{
        area = 'dependency'
        operation = 'none'
        population = 'policies, roles and obligations that require a capability'
        identity = $identityKind; method = $identityMethod
        result = 'not-supported'
        reason = 'this product collects no dependency evidence'
        owner = 'implementation'
    }
)

Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
        -Resource ([ordered]@{
            workload = 'microsoft-365'; type = 'tenant'
            native_id = $TenantHost
            tenant = [ordered]@{ id = $null; host = $TenantHost; how = 'requested' }
            scope = 'tenant'; parent = $null
            display_name = $TenantHost; url = 'https://admin.microsoft.com'
        }) `
        -Facts (Get-LicensingFacts -SubscribedSkus $skus -Assignments $assignments `
            -ReportSettings $settings -UsageWindows $windows -Attempts $attempts) `
        -Requested @('assignment', 'usage_identity', 'usage', 'dependency') `
        -Completed (@('assignment') +
            $(if ($null -ne $settings -and -not $settings.display_concealed_names) {
                    @('usage_identity')
                } else { @() }) +
            $(if ($windows) { @('usage') } else { @() })) `
        -Unavailable ([ordered]@{
            # CONCEALED IS AN ANSWER, NOT AN ABSENCE, AND THE THREE MUST NOT LOOK
            # ALIKE. The setting was read and it said the reports will not name
            # anybody: `partial`, because the reading succeeded and what it
            # returned is that attribution is not available. That is a different
            # fact from a setting nobody read, and both are different from a
            # read that failed.
            usage_identity = $(
                if ($null -eq $settings) {
                    New-Unavailable -State 'missing' `
                        -Detail 'The tenant report privacy setting was not read.'
                }
                elseif ($settings.display_concealed_names) {
                    New-Unavailable -State 'partial' -Detail (
                        'The setting was read. Microsoft 365 is configured to conceal ' +
                        'identifiable user information in usage reports, so no usage ' +
                        'figure in this tenant can be attributed to a person.')
                }
                else { $null }
            )
            usage      = $(if ($windows) { $null } else {
                    New-Unavailable -State 'missing' `
                        -Detail 'No reporting period was requested, so no usage report was read.'
                })
            dependency = (New-Unavailable -State 'missing' `
                    -Detail ('Dependency evidence is not collected by this run. What a ' +
                        'capability is required for is not observable from an assignment ' +
                        'or from usage.'))
        }) `
        -SourceApi 'Microsoft Graph v1.0')
