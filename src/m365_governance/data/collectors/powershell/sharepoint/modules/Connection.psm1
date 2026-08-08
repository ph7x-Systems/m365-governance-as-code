<#
    Connection.psm1

    Authenticating, and nothing else. Read-only by construction: the one PnP
    command here opens a session.

    Which URL to connect to is a property of the mode. Sharing settings live on
    the tenant's record of a site, so those modes reach the admin centre even
    when the question is about one site.

    The engineering standard for every file here is one document:
    docs/POWERSHELL-STANDARDS.md
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Modes that connect to the admin centre rather than to a site.
#
# Every mode whose slice passes no -SiteUrl belongs here, and the Python side
# tests that it does: `TenantSharing` was once added to the collector's switch
# and not to this list, which made the mode demand a -SiteUrl its own slice
# never passes. It would have failed on the first tenant run and on no test.
$script:AdminModes = @('TenantSites', 'SiteSharing', 'TenantSharing')

function Connect-Collector {
    <#
        .SYNOPSIS
        Opens a read-only delegated session and returns the host connected to.

        .DESCRIPTION
        The returned host goes into every envelope's provenance, so the caller
        passes it to Initialize-Evidence rather than deriving it a second time.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string] $Mode,
        [Parameter(Mandatory = $true)] [string] $ClientId,
        [Parameter()] [string] $SiteUrl,
        [Parameter()] [string] $TenantUrl,
        [Parameter()] [switch] $DeviceLogin
    )

    $connectUrl = if ($script:AdminModes -contains $Mode) { $TenantUrl } else { $SiteUrl }
    if (-not $connectUrl) {
        $needed = if ($script:AdminModes -contains $Mode) { '-TenantUrl' } else { '-SiteUrl' }
        throw "Mode $Mode needs $needed."
    }
    if ($Mode -eq 'SiteSharing' -and -not $SiteUrl) {
        throw 'Mode SiteSharing needs -SiteUrl as well as -TenantUrl.'
    }

    if ($DeviceLogin) {
        Connect-PnPOnline -Url $connectUrl -DeviceLogin -ClientId $ClientId
    }
    else {
        Connect-PnPOnline -Url $connectUrl -Interactive -ClientId $ClientId
    }

    return ([uri] $connectUrl).Host
}

Export-ModuleMember -Function Connect-Collector
