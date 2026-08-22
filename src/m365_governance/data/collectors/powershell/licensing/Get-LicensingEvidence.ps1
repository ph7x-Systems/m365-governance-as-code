# public-scope-check: this file names the words it forbids. `trial` here is
# Microsoft's own `companySubscription.isTrial`, describing a TENANT's
# subscription, and it is governance evidence rather than this product's
# commercial model. The guard exists to stop pH7x pricing, entitlement and
# trial mechanics reaching a public MIT repository; a vendor field name that
# a collector must record is the opposite of that.
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

    # THE COMMERCIAL SURFACE, AND IT IS OPT-IN. `/directory/subscriptions`
    # returns `companySubscription`, which carries the seats a subscription
    # includes and whether it is a free trial. It is a SEPARATE acquisition
    # against the tenant and a separate decision: a caller that does not ask for
    # it gets a run that says the surface was not read, rather than one that
    # quietly read more of somebody's directory than they expected.
    #
    # IT IS IN THE BETA ENDPOINT. Microsoft marks beta as subject to change and
    # unsupported in production, and that travels with every fact derived from
    # it rather than being noticed later.
    [Parameter()]
    [switch] $IncludeSubscriptions,

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
            -SourceApi 'Microsoft Graph v1.0' -SourceSystem 'Microsoft 365')
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

# THE SKU IS NOT THE UNIT OF CAPABILITY. A service plan is: a SKU is a bundle
# of them, two SKUs can deliver the same plan, and an assignment can disable
# plans it would otherwise carry. Without the plans, nothing here can answer
# what stops working when an assignment changes, which is the question the
# whole capability turns on.
#
# `appliesTo` and `provisioning_status` travel because Microsoft states what
# they mean: only a SKU whose target class is `User` is assignable at all, and
# a plan can be present in the bundle while disabled, in error, or awaiting an
# administrator. A plan that is not `Success` is not a capability somebody has.
$skus = @(Get-MgSubscribedSku -All | ForEach-Object {
        [ordered]@{
            sku               = [string] $_.SkuPartNumber
            sku_id            = [string] $_.SkuId
            applies_to        = [string] $_.AppliesTo
            capability_status = [string] $_.CapabilityStatus
            # FOUR COUNTERS, NOT ONE. `prepaidUnits` is a `licenseUnitsDetail`
            # and Microsoft documents four: `enabled` is the units enabled for
            # the ACTIVE subscription, `warning` the grace period after it
            # expired, `suspended` the units after cancellation that can still
            # be reactivated, and `lockedOut` the units after the customer
            # cancelled. This collector read `enabled` alone and called it
            # `prepaid_units`, which flattens a subscription lifecycle into a
            # single number and loses the difference between capacity a tenant
            # has and capacity it is about to lose.
            #
            # NONE OF THE FOUR IS `SEATS PURCHASED`. That figure is
            # `companySubscription.totalLicenses` on a different surface.
            prepaid_units     = [ordered]@{
                enabled    = [int] $_.PrepaidUnits.Enabled
                warning    = [int] $_.PrepaidUnits.Warning
                suspended  = [int] $_.PrepaidUnits.Suspended
                locked_out = [int] $_.PrepaidUnits.LockedOut
            }
            consumed_units    = [int] $_.ConsumedUnits
            # THE JOIN TO THE COMMERCIAL SURFACE, carried so that reading it
            # later needs no second enumeration. One SKU row can stand for
            # several subscriptions.
            subscription_ids  = @($_.SubscriptionIds | ForEach-Object { [string] $_ })
            service_plans     = @($_.ServicePlans | ForEach-Object {
                    [ordered]@{
                        plan_id             = [string] $_.ServicePlanId
                        plan                = [string] $_.ServicePlanName
                        applies_to          = [string] $_.AppliesTo
                        provisioning_status = [string] $_.ProvisioningStatus
                    }
                })
        }
    })

# THE SEATS ARE NOT ON THE SKU. `prepaidUnits.enabled` is the units enabled for
# the ACTIVE subscription; `companySubscription.totalLicenses` is the number of
# seats a subscription includes. Only the second is a like-for-like unit, and it
# is on a different resource in a different endpoint version.
#
# `unsupported` IS AN ANSWER AND `missing` IS NOT THE SAME ONE. A cloud that
# does not expose this resource is a fact about the platform; a run that did not
# ask is a fact about the run. They are recorded apart.
$subscriptions = $null
$subscriptionSurface = 'not-observed'
$subscriptionReason = ''
$subscriptionOwner = ''
if ($IncludeSubscriptions) {
    try {
        $subscriptions = @(Invoke-MgGraphRequest -Method GET `
                -Uri 'https://graph.microsoft.com/beta/directory/subscriptions' |
            ForEach-Object { $_.value } |
            ForEach-Object {
                [ordered]@{
                    id             = [string] $_.id
                    sku_id         = [string] $_.skuId
                    sku            = [string] $_.skuPartNumber
                    is_trial       = [bool] $_.isTrial
                    total_licenses = [int] $_.totalLicenses
                    status         = [string] $_.status
                    created        = [string] $_.createdDateTime
                }
            })
        $subscriptionSurface = 'observed'
    }
    catch {
        # A REFUSAL AND AN ABSENCE ARE DIFFERENT ANSWERS. A resource the cloud
        # does not have is `unsupported`; anything else is recorded with whose
        # limitation it is and does not become `unsupported` by default.
        $status = $_.Exception.Response.StatusCode.value__
        $subscriptionReason = $_.Exception.Message
        if ($status -eq 404 -or $status -eq 501) {
            $subscriptionSurface = 'unsupported'
            $subscriptionOwner = 'microsoft'
        }
        else {
            $subscriptionOwner = 'tenant-or-identity'
        }
    }
}

$assignments = @(Get-MgUser -All -Property 'id,userPrincipalName,assignedLicenses,accountEnabled' |
    Where-Object { $_.AssignedLicenses.Count -gt 0 } |
    ForEach-Object {
        [ordered]@{
            user     = [string] $_.Id
            enabled  = [bool] $_.AccountEnabled
            # THE FIELD USED TO BE CALLED `service_plans` AND HELD SKU IDS,
            # which is the naming defect that makes a dependency question
            # unanswerable: a consumer reading it believed it had the
            # capabilities and had the bundles.
            #
            # `disabled_plans` travels with each assignment because it is what
            # makes the effective set effective. A SKU carrying twelve plans of
            # which nine are disabled for this person delivers three.
            licenses = @($_.AssignedLicenses | ForEach-Object {
                    [ordered]@{
                        sku_id         = [string] $_.SkuId
                        disabled_plans = @($_.DisabledPlans |
                            ForEach-Object { [string] $_ })
                    }
                })
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
        $csv = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString() + '.csv')
        try {
            Invoke-MgGraphRequest -Method GET -OutputFilePath $csv `
                -Uri "https://graph.microsoft.com/v1.0/reports/$report(period='$Period')"
            $windows += (Read-UsageReport -Path $csv -Report $report `
                    -WindowDays ([int] $Period.Substring(1)))
        }
        catch {
            # A report that refused is not a report that returned nothing, and
            # the difference is the whole point of this family. Whose refusal it
            # was is recorded in the attempt beside it.
            Write-Verbose "$report refused: $($_.Exception.Message)"
        }
        finally {
            if (Test-Path $csv) { Remove-Item $csv -Force -ErrorAction SilentlyContinue }
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
        # A SEPARATE SURFACE AND A SEPARATE DECISION, so it records its own
        # attempt. `not-collected` here means the caller did not ask for it,
        # which is a fact about the run and not about the tenant.
        area = 'capacity'
        operation = 'GET /beta/directory/subscriptions'
        population = 'commercial-subscriptions-of-this-tenant'
        identity = $identityKind; method = $identityMethod
        result = $(switch ($subscriptionSurface) {
                'observed' { 'observed' }
                'unsupported' { 'not-supported' }
                default { 'not-collected' }
            })
        reason = $(switch ($subscriptionSurface) {
                'observed' { '' }
                'unsupported' { $subscriptionReason }
                default { if ($subscriptionReason) { $subscriptionReason } else { 'the caller did not ask for the commercial subscriptions' } }
            })
        owner = $(switch ($subscriptionSurface) {
                'observed' { '' }
                'unsupported' { 'microsoft' }
                default { if ($subscriptionOwner) { $subscriptionOwner } else { 'caller' } }
            })
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
            -ReportSettings $settings -UsageWindows $windows -Attempts $attempts `
            -Subscriptions $subscriptions -SubscriptionSurface $subscriptionSurface) `
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
                    # NAMED SCOPE, NOT A CLAIM ABOUT THE WHOLE TENANT. The
                    # earlier wording said no usage figure in this tenant could be
                    # attributed to anybody, which is wider than what
                    # `adminReportSettings` governs. Microsoft states the reach:
                    # the admin centre reports, the Microsoft 365 usage reports in
                    # Graph and Power BI, and the Teams admin centre reports. A
                    # usage source outside that list is not covered by this
                    # observation, and this sentence no longer implies it is.
                    New-Unavailable -State 'partial' -Detail (
                        'The setting was read. Microsoft 365 is configured to conceal ' +
                        'identifiable user information in the usage reports this ' +
                        'setting covers: the admin centre reports, the Microsoft 365 ' +
                        'usage reports in Microsoft Graph and Power BI, and the Teams ' +
                        'admin centre reports.')
                }
                else { $null }
            )
            usage      = $(if ($windows) { $null } else {
                    New-Unavailable -State 'missing' `
                        -Detail 'No reporting period was requested, so no usage report was read.'
                })
            # COVERAGE AND THE FACT HAVE TO AGREE, and they did not. The fact
            # moved to `partial` when the collector learnt to calculate what one
            # assignment uniquely delivers, and this entry still said the area
            # was not read at all. A consumer renders coverage: the desktop
            # client showed `dependency: not read` beside evidence that had
            # just calculated part of it, which is the product contradicting
            # itself on one screen. Found by opening the real binary against a
            # real bundle and looking at it.
            dependency = (New-Unavailable -State 'partial' `
                    -Detail ('Part of this was read: what one assignment uniquely ' +
                        'delivers is calculated from the service plans and the ' +
                        'plans disabled on each assignment. What a capability is ' +
                        'REQUIRED FOR -- a policy, a role, an obligation, a ' +
                        'workload that would stop -- is not observable from an ' +
                        'assignment or from usage, and nothing may be concluded ' +
                        'about removing a licence without it.'))
        }) `
        -SourceApi 'Microsoft Graph v1.0' -SourceSystem 'Microsoft 365')
