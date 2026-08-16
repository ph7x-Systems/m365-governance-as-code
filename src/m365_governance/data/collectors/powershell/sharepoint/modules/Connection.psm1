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

    # `Connect` takes whichever address it was given, and prefers the admin
    # centre. It is a reachability check rather than a slice, so it has no
    # opinion about which endpoint the caller intends to collect from -- and
    # refusing it for the wrong one would answer a question nobody asked.
    if ($Mode -eq 'Connect') {
        $connectUrl = if ($TenantUrl) { $TenantUrl } else { $SiteUrl }
        if (-not $connectUrl) { throw 'Mode Connect needs -TenantUrl or -SiteUrl.' }
    }
    else {
        $connectUrl = if ($script:AdminModes -contains $Mode) { $TenantUrl } else { $SiteUrl }
        if (-not $connectUrl) {
            $needed = if ($script:AdminModes -contains $Mode) { '-TenantUrl' } else { '-SiteUrl' }
            throw "Mode $Mode needs $needed."
        }
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

function Get-ConnectionFacts {
    <#
        .SYNOPSIS
        What the open session turned out to be. Never what it might be.

        .DESCRIPTION
        Read from PnP.PowerShell's own connection object rather than restated
        from the arguments: the point of connecting is to find out, and echoing
        back what was asked for would answer a different question.

        WHAT IS DELIBERATELY ABSENT. The connection object also exposes
        ClientSecret, Certificate and PSCredential. None of them is read here
        and none may ever be: a command that printed a credential would put one
        into a terminal, a log and whatever captured that log.

        THE DIRECTORY IDENTITY IS NOT HERE EITHER, and that is the honest
        answer rather than an omission. `tenant.id` is null throughout this
        engine because no collection path for it is proven on a real tenant.
        A documented candidate exists -- Get-PnPTenantId -TenantUrl -- and it
        is recorded in docs/COLLECTION-PATH-AUDIT.md as needs-tenant-validation.
        Until a run settles it, a host is an address and nothing establishes
        which directory it belongs to.
    #>
    [CmdletBinding()]
    param(
        # Passed in rather than read from a script variable. `$script:TenantHost`
        # belongs to Evidence.psm1, and a module scope is not shared: reading it
        # here would have silently produced an empty host.
        [Parameter(Mandatory = $true)] [string] $TenantHost
    )

    $connection = Get-PnPConnection

    # Interactive and device sign-in are both delegated: the session sees what
    # one person sees. Recording the flow separately from the identity kind
    # keeps two different questions apart.
    [ordered]@{
        connected        = $true
        host             = $TenantHost
        url              = [string] $connection.Url
        client_id        = [string] $connection.ClientId
        identity_kind    = 'delegated'
        connection_type  = [string] $connection.ConnectionType
        scopes           = @($connection.Scopes)
        tenant_directory = $null
    }
}

Export-ModuleMember -Function Connect-Collector, Get-TenantHost, Get-ConnectionFacts
