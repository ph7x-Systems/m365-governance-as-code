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

function Read-CertificatePassword {
    <#
        .SYNOPSIS
        The PFX password, from the environment, as a SecureString.

        .DESCRIPTION
        What crosses the command line is the NAME of a variable. A value there
        is in the shell history and in the process list of every user on the
        machine, and it stays in both long after the run.

        PSAvoidUsingConvertToSecureStringWithPlainText is right in general and
        does not apply here. An environment variable IS a string, and
        `Connect-PnPOnline -CertificatePassword` takes a SecureString: there is
        no API that reads one straight into the other, so this conversion is
        the narrowest bridge between them and the plain copy does not outlive
        the function.
    #>
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
        'PSAvoidUsingConvertToSecureStringWithPlainText', '',
        Justification = 'An environment variable is a string; PnP requires a SecureString.')]
    [CmdletBinding()]
    param([Parameter()] [string] $VariableName)

    if (-not $VariableName) { return $null }
    $raw = [Environment]::GetEnvironmentVariable($VariableName)
    if ([string]::IsNullOrEmpty($raw)) {
        throw "-CertificatePasswordEnv names $VariableName, and that variable is empty or unset."
    }
    return (ConvertTo-SecureString -String $raw -AsPlainText -Force)
}

function Assert-AddressIsResolvable {
    <#
        .SYNOPSIS
        Refuses an interactive sign-in to an address no directory owns.

        .DESCRIPTION
        AN INTERACTIVE SIGN-IN GOES SOMEWHERE. Where public discovery cannot
        say which directory owns an address, it will not be this one: the
        sign-in falls back to the directory the browser is already signed into,
        and whatever comes back is then reported as an answer about the address
        that was typed.

        Observed on 2026-08-20 against a live tenant, from a host that does not
        exist: a browser opened against an unrelated directory and returned
        AADSTS700016 -- a true sentence about the wrong tenant.

        AND IN A COLLECTION IT IS WORSE THAN A WRONG MESSAGE. `tenant.id` is
        null throughout this engine, so the evidence contract says the host
        carries the identity -- and the host is derived from the URL the caller
        asked for, never from the session. A collection that signed in
        somewhere else would stamp its provenance with a tenant the session
        never established.

        THE ENGINE HAD THIS EVIDENCE AND USED IT FOR NOTHING. It asked which
        directory owns the address, was told nothing does, and signed in
        anyway. An absence never authorises the step that depends on it.

        A CERTIFICATE PROCEEDS. `-Tenant` names the directory, so the caller
        said where the token comes from and discovery is not the only thing
        that knew.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string] $Url,
        [Parameter()] [string] $CertificatePath
    )

    if ($CertificatePath) { return }

    $resolved = Resolve-TenantAddress -Url $Url
    if ($resolved.resolved_tenant_id) { return }

    throw ("No directory owns $Url, so an interactive sign-in would " +
        'authenticate against whichever directory this browser is already ' +
        'signed into, and report the result as an answer about this address. ' +
        'Check the address, or name the directory with a certificate. ' +
        'Discovery said: ' + $resolved.detail)
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
        [Parameter()] [switch] $DeviceLogin,
        # APP-ONLY, AND IT IS A DIFFERENT IDENTITY RATHER THAN A DIFFERENT
        # PROMPT. Interactive and device login are both delegated: the run sees
        # what one person sees. A certificate authenticates the APPLICATION,
        # and what it sees is what the tenant granted the application. An
        # administrator has to be able to run the same collection unattended
        # without the collector or the evidence changing shape.
        [Parameter()] [string] $CertificatePath,
        [Parameter()] [string] $TenantId,
        # A SecureString, never a plain one, and never from the command line.
        # The caller reads it from the environment or from stdin: an argument
        # is in the shell history and in the process list of every user on the
        # machine.
        [Parameter()] [securestring] $CertificatePassword
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

    # THE TWO MODES ARE EXCLUSIVE, and the refusal is here as well as in the
    # command line: a script that silently preferred one would authenticate as
    # somebody the caller did not choose, and the evidence would say so without
    # anybody noticing.
    if ($CertificatePath -and $DeviceLogin) {
        throw 'Choose one: -CertificatePath authenticates the application, -DeviceLogin authenticates a person.'
    }

    # BEFORE ANY SIGN-IN, AND FOR EVERY MODE. This used to run in the script,
    # inside `if ($Mode -eq 'Connect')`, so the one command that writes nothing
    # was guarded and the ten that write evidence were not.
    Assert-AddressIsResolvable -Url $connectUrl -CertificatePath $CertificatePath

    if ($CertificatePath) {
        if (-not $TenantId) { throw '-CertificatePath needs -TenantId.' }
        if (-not (Test-Path -LiteralPath $CertificatePath)) {
            throw "-CertificatePath does not exist: $CertificatePath"
        }
        $parameters = @{
            Url             = $connectUrl
            ClientId        = $ClientId
            Tenant          = $TenantId
            CertificatePath = $CertificatePath
        }
        # Omitted rather than passed empty: a certificate with no password is a
        # supported case, and an empty SecureString is not the same thing.
        if ($CertificatePassword) {
            $parameters['CertificatePassword'] = $CertificatePassword
        }
        Connect-PnPOnline @parameters
    }
    elseif ($DeviceLogin) {
        Connect-PnPOnline -Url $connectUrl -DeviceLogin -ClientId $ClientId
    }
    else {
        Connect-PnPOnline -Url $connectUrl -Interactive -ClientId $ClientId
    }

    return Get-TenantHost -Url $connectUrl
}

function Resolve-TenantAddress {
    <#
        .SYNOPSIS
        Which directory owns an address. A different question from who is signed in.

        .DESCRIPTION
        `Get-PnPTenantId -TenantUrl` is documented as not requiring an active
        connection, and it does not: measured against a real tenant with an
        empty MSAL cache, no prior connection and no client id, and separately
        against the discovery endpoint itself with no authorization header at
        all.

        SO THIS RESOLVES AN ADDRESS AND OBSERVES NOTHING. It answers "which
        directory owns this host", authoritatively, from public OpenID
        discovery. It does not answer "which directory is this session
        operating in", which only an authenticated session can answer.

        The two must not be one field. A GUID anybody in the world can obtain
        without ever reaching the tenant is not evidence that a collection
        looked at that tenant.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string] $Url
    )

    try {
        [ordered]@{
            host             = Get-TenantHost -Url $Url
            resolved_tenant_id = [string] (Get-PnPTenantId -TenantUrl $Url)
            how              = 'public-discovery'
            detail           = $null
        }
    }
    catch {
        # A host that does not exist fails here, named, rather than resolving to
        # nothing. Reported rather than thrown: the sign-in may still be worth
        # attempting, and a caller deserves both answers.
        [ordered]@{
            host             = Get-TenantHost -Url $Url
            resolved_tenant_id = $null
            how              = 'public-discovery'
            detail           = [string] $_.Exception.Message
        }
    }
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
        [Parameter(Mandatory = $true)] [string] $TenantHost,

        # WHICH IDENTITY SIGNED IN, decided by the caller from how the
        # connection was made rather than guessed from the session object.
        # It was hardcoded to 'delegated' here, which meant that a run
        # authenticating as the application reported itself as a person -- in
        # the one field that decides what an empty result means.
        [Parameter()] [ValidateSet('delegated', 'application')]
        [string] $IdentityKind = 'delegated',

        [Parameter()] [ValidateSet('interactive', 'device-code', 'certificate')]
        [string] $IdentityMethod = 'interactive'
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
        identity_kind    = $IdentityKind
        identity_method  = $IdentityMethod
        connection_type  = [string] $connection.ConnectionType
        scopes           = @($connection.Scopes)
        # WHICH DIRECTORY THIS SESSION IS OPERATING IN, and null until something
        # reads it from the session itself. Deliberately NOT the value that
        # resolving the address returns: that one is authoritative about the
        # address and says nothing about who signed in.
        observed_tenant_id = $null
    }
}

function Test-CollectorAuthorization {
    <#
        .SYNOPSIS
        Whether this identity may READ, which is a different question from
        whether it signed in.

        .DESCRIPTION
        Connect-PnPOnline succeeds with zero permissions granted. A product
        that stops at the sign-in has verified authentication and reported
        authorization, and the reader cannot tell the difference until a
        collection several minutes long comes back empty.

        One read, the cheapest that the rules actually need: the web at the
        address the caller gave. It is read-only, it is the same call the
        collectors make first, and it is the smallest thing that can prove a
        denial rather than predict one.

        NOT ATTEMPTED IS AN ANSWER. Without a site address there is nothing to
        read yet, and saying so is honest where inventing a target would not
        be. It is never reported as established.
    #>
    [CmdletBinding()]
    param(
        [Parameter()] [string] $SiteUrl
    )

    if (-not $SiteUrl) {
        return [ordered]@{
            state  = 'not-attempted'
            detail = 'no site address was given, so no read was attempted'
            read   = $null
        }
    }

    try {
        $web = Get-PnPWeb -ErrorAction Stop
        return [ordered]@{
            state  = 'established'
            detail = 'read one web at the address given'
            read   = [string] $web.Url
        }
    }
    catch {
        return [ordered]@{
            state  = 'denied'
            detail = [string] $_.Exception.Message
            read   = $null
        }
    }
}

Export-ModuleMember -Function Read-CertificatePassword, Connect-Collector, Get-TenantHost, Get-ConnectionFacts, Resolve-TenantAddress, Test-CollectorAuthorization, Assert-AddressIsResolvable
