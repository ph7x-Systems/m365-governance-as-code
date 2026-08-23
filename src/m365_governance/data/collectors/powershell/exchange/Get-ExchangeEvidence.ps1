<#
.SYNOPSIS
    Exchange Online evidence: whether mail can leave this organisation
    automatically, and by which route.

.DESCRIPTION
    A THIRD ACQUISITION SURFACE. The SharePoint collector reads through PnP and
    the licensing collector reads Microsoft Graph; this reads Exchange Online
    through its own module, under its own permissions, with its own sign-in.

    WHAT IT ANSWERS. Automatic external forwarding is governed by three
    controls that no screen shows together, and Microsoft documents that they
    interact rather than override: "When one setting allows external
    forwarding, but another setting blocks external forwarding, the block
    typically wins." A reader who has checked one has checked a third.

    WHAT IT REFUSES TO DO. It produces no conclusion about whether an
    organisation should permit forwarding. Forwarding is a legitimate business
    arrangement in many organisations and Microsoft publishes no rule that it
    must be off. What it reports is which controls are in which position and
    what each of them does not reach.

    THE PREREQUISITE IS EVIDENCE, NOT A CRASH. `ExchangeOnlineManagement` is a
    separate install and is frequently absent. A collector that threw on the
    import would be indistinguishable, to a caller, from a tenant that returned
    nothing.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
# Same reasoning as the SharePoint collector, and the same two suppressions.
# `-CertificatePasswordEnv` takes the NAME of an environment variable, not a
# password: taking a SecureString instead would mean the caller had the plain
# value in their own shell first, which is the thing this avoids. And the
# conversion below reads that variable, which is the only way to hand the
# module a credential without the caller typing one.
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSAvoidUsingPlainTextForPassword', 'CertificatePasswordEnv',
    Justification = 'The value is the name of an environment variable, not a password.')]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute(
    'PSAvoidUsingConvertToSecureStringWithPlainText', '',
    Justification = 'The plain value is read from the environment variable the caller named, never from a literal.')]
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Connect', 'Forwarding')]
    [string] $Mode,

    [Parameter()]
    [string] $OutputPath,

    [Parameter()]
    [string] $TenantHost,

    [Parameter()]
    [string] $ClientId,

    # PASSED BY THE ENGINE WHENEVER A CERTIFICATE IS USED, AND USED HERE.
    # Exchange Online identifies the organisation by its domain rather than by
    # a directory id, so this is a fallback for `-Organization` rather than the
    # primary: a caller that supplies only the tenant id still connects.
    [Parameter()]
    [string] $TenantId,

    [Parameter()]
    [string] $CertificatePath,

    [Parameter()]
    [string] $CertificatePasswordEnv,

    [Parameter()]
    [switch] $DeviceLogin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Modules = Join-Path $PSScriptRoot 'modules'
Import-Module (Join-Path (Split-Path $PSScriptRoot -Parent) 'sharepoint/modules/Evidence.psm1') -Force
Import-Module (Join-Path $Modules 'Forwarding.psm1') -Force

# THE MODULE IS A FACT ABOUT THIS MACHINE, NOT ABOUT THE TENANT. Reported as
# `not-supported` naming what is missing, so a caller can tell an absent
# dependency from an organisation that has nothing to report.
$missing = @()
if (-not (Get-Module -ListAvailable -Name 'ExchangeOnlineManagement')) {
    $missing += 'ExchangeOnlineManagement'
}

if ($missing.Count -gt 0) {
    Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
            -Resource ([ordered]@{
                workload = 'exchange'; type = 'tenant'
                native_id = $TenantHost
                tenant = [ordered]@{ id = $null; host = $TenantHost; how = 'requested' }
                scope = 'tenant'; parent = $null
                display_name = $TenantHost; url = 'https://admin.exchange.microsoft.com'
            }) `
            -Facts ([ordered]@{
                forwarding = [ordered]@{
                    outbound_policies = New-AbsentFact -State 'not-supported' -Detail (
                        "The PowerShell module $($missing -join ', ') is not installed on " +
                        'this machine, so nothing was read. This is a fact about the machine ' +
                        'that ran the collection and says nothing about the organisation.')
                }
            }) `
            -Requested @('forwarding') -Completed @() `
            -Unavailable ([ordered]@{
                forwarding = [ordered]@{
                    state = 'not-supported'
                    detail = "requires $($missing -join ', ')"
                }
            }) `
            -SourceApi 'ExchangeOnlineManagement')
    return
}

Import-Module ExchangeOnlineManagement -ErrorAction Stop

$identityKind = if ($CertificatePath) { 'application' } else { 'delegated' }
$identityMethod = if ($CertificatePath) { 'certificate' } elseif ($DeviceLogin) { 'device-code' } else { 'interactive' }

if ($CertificatePath) {
    $password = if ($CertificatePasswordEnv) {
        ConvertTo-SecureString ([Environment]::GetEnvironmentVariable($CertificatePasswordEnv)) -AsPlainText -Force
    }
    else { $null }
    $organization = if ($TenantHost) { $TenantHost } else { $TenantId }
    Connect-ExchangeOnline -AppId $ClientId -Organization $organization `
        -CertificateFilePath $CertificatePath -CertificatePassword $password `
        -ShowBanner:$false
}
elseif ($DeviceLogin) {
    Connect-ExchangeOnline -Device -ShowBanner:$false
}
else {
    Connect-ExchangeOnline -ShowBanner:$false
}

if ($Mode -eq 'Connect') {
    # The address and the identity, and nothing about the organisation. Same
    # contract as every other collector's Connect: it proves a session opened.
    Write-Output "connected: $TenantHost as $identityKind/$identityMethod"
    return
}

Write-Evidence -Path $OutputPath -Evidence (New-Evidence `
        -Resource ([ordered]@{
            workload = 'exchange'; type = 'tenant'
            native_id = $TenantHost
            tenant = [ordered]@{ id = $null; host = $TenantHost; how = 'requested' }
            scope = 'tenant'; parent = $null
            display_name = $TenantHost; url = 'https://admin.exchange.microsoft.com'
        }) `
        -Facts (Get-ForwardingFact) `
        -Requested @('forwarding') -Completed @('forwarding') `
        -Unavailable ([ordered]@{}) `
        -SourceApi 'ExchangeOnlineManagement')
