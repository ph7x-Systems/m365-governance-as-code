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

function Get-TenantHost {
    <#
        .SYNOPSIS
        The tenant a URL belongs to, which is not always the URL's own host.

        .DESCRIPTION
        The admin centre lives on a different host from the sites it
        administers. Microsoft documents the format as

            https://{your-tenant-prefix}-admin.sharepoint.com

        with the same shape per cloud (`.sharepoint.us` for GCC High), so only
        the first label differs and removing the suffix from it is a documented
        mapping rather than a guess.

        https://learn.microsoft.com/sharepoint/dev/spfx/set-up-your-developer-tenant

        WHY THIS EXISTS. The collector used to record the host it happened to
        connect to. A tenant collected through the admin centre and the same
        tenant collected through one of its sites then produced two different
        tenant identities, so evidence gathered by two modes on one Tuesday
        could never be assembled into one assessment. Nothing caught it,
        because nothing compared the two until an assessment tried to.

        KNOWN LIMIT, RECORDED RATHER THAN PAPERED OVER. In multi-geo, satellite
        sites live on their own hosts and this returns the satellite rather than
        the primary. The mapping above is only documented for the admin centre.
        Resolving it properly needs the tenant's directory id, and no collection
        path for that has been proven on a tenant yet, so nothing here pretends
        to have one.
    #>
    param([Parameter(Mandatory = $true)] [string] $Url)

    $hostName = ([uri] $Url).Host
    $labels = $hostName.Split('.')
    if ($labels[0] -like '*-admin') {
        $labels[0] = $labels[0].Substring(0, $labels[0].Length - '-admin'.Length)
    }
    return ($labels -join '.')
}

function Connect-Collector {
    <#
        .SYNOPSIS
        Opens a read-only delegated session and returns the tenant connected to.

        .DESCRIPTION
        The returned host goes into every envelope's provenance, so the caller
        passes it to Initialize-Evidence rather than deriving it a second time.
        It is the tenant's host and not the connection's: see Get-TenantHost.
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

    return Get-TenantHost -Url $connectUrl
}

Export-ModuleMember -Function Connect-Collector, Get-TenantHost
