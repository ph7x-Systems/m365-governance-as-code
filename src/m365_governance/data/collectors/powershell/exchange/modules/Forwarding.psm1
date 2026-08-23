<#
.SYNOPSIS
    Whether mail can leave this organisation automatically, and by which route.

.DESCRIPTION
    THERE ARE THREE GATES AND THEY ARE NOT THE SAME GATE.

    Microsoft documents them separately and states how they interact: "When one
    setting allows external forwarding, but another setting blocks external
    forwarding, the block typically wins." So a reader who has checked one and
    concluded that mail cannot leave has checked a third of the question.

      * the outbound spam filter policy decides whether a user may forward
        externally at all;
      * a remote domain decides where forwarded mail may go;
      * a mail flow rule can forward regardless of either.

    AND ONE OF THE THREE HAS A VALUE WHOSE MEANING IS NOT IN THE VALUE.
    `AutoForwardingMode: Automatic` was equivalent to On when introduced; in
    2021 it became Off for new organisations and for existing ones that were
    not actively using it, and stayed On for those that were. Microsoft's own
    instruction is to stop using it: "Because the behavior can differ by
    organization, configure On - Forwarding is enabled or Off - Forwarding is
    disabled instead of Automatic - System-controlled."

    An administrator reading `Automatic` in their own tenant cannot tell which
    way it runs. That is not this engine's opinion about a setting; it is the
    vendor documenting that the setting does not carry its own meaning.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-OutboundForwardingFact {
    <#
        The outbound spam filter policies, and what each says about forwarding.

        Every policy, not only the default: a custom policy scoped to some
        recipients decides for them, and reading the default alone would report
        the tenant as one thing when it is several.
    #>
    param()

    $facts = [ordered]@{}
    try {
        $policies = @(Get-HostedOutboundSpamFilterPolicy -ErrorAction Stop)
    }
    catch {
        return [ordered]@{
            outbound_policies = New-AbsentFact -State 'permission-denied' -Detail (
                'The outbound spam filter policies were not readable by this identity: ' +
                $_.Exception.Message)
            outbound_policies_ambiguous = New-AbsentFact -State 'permission-denied' -Detail (
                'Not counted, because the policies themselves were not readable.')
        }
    }

    $modes = @($policies | ForEach-Object {
            [ordered]@{
                name = [string] $_.Name
                auto_forwarding_mode = [string] $_.AutoForwardingMode
                is_default = [bool] $_.IsDefault
            }
        })

    $facts['outbound_policies'] = New-ScalarFact -Value $modes `
        -RawField 'Get-HostedOutboundSpamFilterPolicy: Name, AutoForwardingMode, IsDefault'

    # THE COUNT A RULE READS. `Automatic` is the value whose behaviour is not
    # determined by the value, so what a rule needs is how many policies are
    # sitting on it -- and a count is a fact about the tenant rather than a
    # judgement about it.
    $ambiguous = @($modes | Where-Object { $_.auto_forwarding_mode -eq 'Automatic' })
    $facts['outbound_policies_ambiguous'] = New-ScalarFact -Value $ambiguous.Count `
        -RawField 'AutoForwardingMode -eq Automatic, counted over every outbound spam filter policy'

    return $facts
}

function Get-RemoteDomainFact {
    <#
        Where forwarded mail may go, and what that control does not reach.

        `AutoForwardEnabled` on a remote domain overrides a USER's forwarding.
        Microsoft states the limit in the same table: "When admins use other
        methods to configure automatic forwarding for users, the forwarded
        messages aren't affected by the remote domain settings" -- mailbox
        forwarding set by an administrator, and mail flow rules, go anyway.
    #>
    param()

    $facts = [ordered]@{}
    try {
        $domains = @(Get-RemoteDomain -ErrorAction Stop)
    }
    catch {
        return [ordered]@{
            remote_domains = New-AbsentFact -State 'permission-denied' -Detail (
                'The remote domains were not readable by this identity: ' +
                $_.Exception.Message)
            remote_domains_allowing_forwarding = New-AbsentFact -State 'permission-denied' -Detail (
                'Not counted, because the domains themselves were not readable.')
        }
    }

    $rows = @($domains | ForEach-Object {
            [ordered]@{
                name = [string] $_.Name
                domain_name = [string] $_.DomainName
                auto_forward_enabled = [bool] $_.AutoForwardEnabled
            }
        })

    $facts['remote_domains'] = New-ScalarFact -Value $rows `
        -RawField 'Get-RemoteDomain: Name, DomainName, AutoForwardEnabled'
    $facts['remote_domains_allowing_forwarding'] = New-ScalarFact `
        -Value (@($rows | Where-Object { $_.auto_forward_enabled }).Count) `
        -RawField 'AutoForwardEnabled -eq $true, counted over every remote domain'

    # WHAT A BLOCK HERE DOES NOT STOP, carried as evidence rather than left to
    # be remembered by whoever reads the count above.
    $facts['remote_domain_block_reaches'] = New-ScalarFact `
        -Value 'user-configured forwarding only' `
        -RawField 'documented: admin-configured mailbox forwarding and mail flow rules are not affected by remote domain settings'

    return $facts
}

function Get-ForwardingFact {
    <#
        The three gates, as one fact family.

        Two are read and one is named and not read. Mail flow rules can forward
        regardless of the other two, and enumerating them is a separate reading
        with a separate question behind it -- so their absence is recorded as
        `not-supported` rather than left to be read as `none`.
    #>
    param()

    $f = [ordered]@{}
    foreach ($entry in (Get-OutboundForwardingFact).GetEnumerator()) { $f[$entry.Key] = $entry.Value }
    foreach ($entry in (Get-RemoteDomainFact).GetEnumerator()) { $f[$entry.Key] = $entry.Value }

    # THE THIRD GATE, NAMED AND NOT READ. Mail flow rules can forward
    # regardless of the two above, and enumerating them is a separate reading
    # with a separate question behind it. Absent is not none.
    $f['mail_flow_rules'] = New-AbsentFact -State 'not-supported' -Detail (
        'Mail flow rules are not read by this collector. They are the third route ' +
        'by which mail leaves automatically, they are not affected by remote domain ' +
        'settings, and whether any of them forwards externally is a question about ' +
        'rule actions rather than about a forwarding setting.')

    return [ordered]@{ forwarding = $f }
}

Export-ModuleMember -Function Get-ForwardingFact
