# The command line

**Owner decision, 2026-11-11.** The command line is regrouped so that a person
can sign in once and then work by commands, in the manner of other Microsoft
365 command lines, without changing what the engine establishes: evidence,
provenance, schemas, exit codes and the first-run contract stay as they are.
This file owns the shape of the command line. `docs/FIRST-RUN-CONTRACT.md`
owns the journey; the two do not restate each other.

## What may never break

The surface published before the regrouping is frozen in
`tests/frozen/cli-v1-surface.json` and held by
`tests/test_cli_compatibility.py`: nineteen commands, every option each took,
every value an option accepted, both executable names (`m365g` and
`m365-governance`, charter `D87`), and the meaning of the exit codes — `0` a
result, `1` a negative result, `2` a refusal. Consumers invoke this engine as a
subprocess by those names. A new name is an addition and never a replacement.

## Sessions

A session is kept between commands **only after `m365g login`**, which is the
operator's explicit choice. Without it every command authenticates for itself
and leaves nothing behind, exactly as before.

- **Where the token is.** In the operating system's protected storage, written
  by the sign-in library and never by this engine: the macOS Keychain, Windows
  data protection, or the Linux keyring. This engine holds no token, prints
  none and writes none into evidence.
- **Plain text is refused.** On Linux the library falls back to an unprotected
  file when no keyring answers. `login` refuses to persist where it cannot
  establish protected storage, and checks the result afterwards: a readable
  token cache is cleared and the login fails.
- **What this engine records.** A connection's name, tenant address, directory,
  application registration, sign-in method, the identity the session reported
  and when — in `connections.json` under the user's configuration directory
  (`M365G_HOME` overrides it). It refuses to hold a secret.
- **One identity per tenant and application registration.** The library keys a
  persisted sign-in by those two; which account it would choose among several
  is not established, so a second `login` for the same pair replaces the first.
- **A session is not an authorization.** `login` and `connect` report the two
  separately, as the first-run contract requires. `status` reads the local
  record and reaches no tenant; `connect` is the command that asks the tenant.
- **A session is used only for its own tenant.** A command aimed at another
  tenant, by an option or a project file, ignores the active connection and
  says so.

Precedence, for the application registration and the tenant address: an option
on the command line, then a project file, then the active connection.

## What a session does not cover

Twelve of the sixteen collections sign in through PnP.PowerShell and reuse a
persisted session. `conditional-access` and `tenant-governance` read Microsoft
Graph with a certificate and never prompt. `licensing` signs in through the
Microsoft Graph PowerShell SDK, whose own persisted context is shared with
everything else the operator does with that SDK: the collector confines its
sign-in to its own process, so it neither leaves that context behind nor uses
one that was already there, and it prompts on every delegated run.
`forwarding` signs in through Exchange Online PowerShell, which keeps no
session between processes, and prompts on every delegated run.

## The commands

| Command | What it does | Reaches a tenant |
|---|---|---|
| `login` | signs in, reports authentication and authorization apart, keeps the session | yes |
| `status` | the active connection, from the local record | no |
| `logout` | removes the stored sign-in and its record (`--name`, `--all`) | yes, to clear a persisted sign-in |
| `connection list` | every stored connection | no |
| `connection use NAME` | makes one the active connection | no |
| `connection remove NAME` | as `logout --name NAME` | as `logout` |

`connect`, `collect` and `run` take `--connection NAME`; without it they use
the active connection when it is for the tenant they are aimed at.

Who signed in is not in the record: the session reports the kind of identity
and the method, and no collection path for the person's name is established.
A logout that cannot clear the stored sign-in keeps the record and exits `1`,
so that it is not mistaken for a logout.

## Groups

A command is found by its service, then the thing, then what to do with it.
**A grouped command is the earlier command by another name**: it is rewritten
to it before anything is parsed (`grouping.py`), so both take the same options,
behave the same and exit the same, and neither is deprecated. A group named on
its own (`m365g spo`) lists what it holds and reaches nothing.

The groups name what this engine already does. A collection is still a
collection: `m365g spo site list` writes evidence, as `m365g collect sites`
does, and takes the same `--output`.

| Grouped | Earlier name |
|---|---|
| `m365g spo site list` | `m365g collect sites` |
| `m365g spo owner list` | `m365g collect owners` |
| `m365g spo sharing get` | `m365g collect sharing` |
| `m365g spo tenant sharing get` | `m365g collect tenant-sharing` |
| `m365g spo permission list` | `m365g collect permissions` |
| `m365g spo activity get` | `m365g collect activity` |
| `m365g spo classification get` | `m365g collect classification` |
| `m365g spo modernity get` | `m365g collect modernity` |
| `m365g spo customization get` | `m365g collect customization` |
| `m365g spo spfx list` | `m365g collect spfx` |
| `m365g spo agent list` | `m365g collect agents` |
| `m365g spo brandcenter get` | `m365g collect brand-center` |
| `m365g entra ca list` | `m365g collect conditional-access` |
| `m365g entra tenant governance get` | `m365g collect tenant-governance` |
| `m365g entra license list` | `m365g collect licensing` |
| `m365g exo forwarding get` | `m365g collect forwarding` |
| `m365g evidence collect` | `m365g collect` |
| `m365g evidence stats` | `m365g stats` |
| `m365g evidence evaluate` | `m365g evaluate` |
| `m365g governance run` | `m365g run` |
| `m365g governance assess` | `m365g assess` |
| `m365g governance verify` | `m365g verify` |
| `m365g governance report` | `m365g report` |
| `m365g governance diff` | `m365g diff` |
| `m365g rule list` | `m365g list-rules` |
| `m365g rule show` | `m365g show-rule` |
| `m365g rule get` | `m365g show-rule` |
| `m365g rule validate` | `m365g validate` |
| `m365g rule explain` | `m365g explain` |
| `m365g migration read` | `m365g migration-read` |
| `m365g migration verify` | `m365g migration-verify` |
| `m365g engine doctor` | `m365g doctor` |
| `m365g engine setup` | `m365g setup` |
| `m365g engine capabilities` | `m365g capabilities` |
| `m365g engine contracts` | `m365g contracts` |

`login`, `status`, `logout`, `connection` and `connect` stay at the top level:
signing in and asking the tenant come before choosing a service.
