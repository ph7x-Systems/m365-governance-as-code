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

Every SharePoint collection signs in through PnP.PowerShell and reuses a
persisted session; `m365g engine capabilities` lists them, and no count is
kept here to go stale. The Microsoft Graph reads (`conditional-access`, `tenant-governance`,
`guests`, `applications`, `groups`) sign in as the same person through the same
registration, for the scopes their collector declares, unless a certificate
or a token in the environment says otherwise. `licensing` signs in through the
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
| `m365g entra guest list` | `m365g collect guests` |
| `m365g entra app list` | `m365g collect applications` |
| `m365g entra serviceprincipal list` | `m365g collect service-principals` |
| `m365g entra group list` | `m365g collect groups` |
| `m365g teams team list` | `m365g collect groups --where group.is_team=true` |
| `m365g spo site list` | `m365g collect sites` |
| `m365g spo hub list` | `m365g collect hubs` |
| `m365g spo site admins` | `m365g collect sites-owners` |
| `m365g spo site guests` | `m365g collect sites-guests` |
| `m365g spo owner list` | `m365g collect owners` |
| `m365g spo sharing get` | `m365g collect sharing` |
| `m365g spo sharing list` | `m365g collect sites-sharing` |
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

## Composed scenarios

`m365g governance inspect SCENARIO --evidence DIRECTORY` answers one question
from several collections. It reads evidence already collected and reaches no
tenant, so the same evidence always gives the same answer. It is not an
assessment: it reaches no outcome, counts nothing as good or bad, and
publishes no total over unlike things.

| Scenario | Reads | Option |
|---|---|---|
| `external-access` | `sites-sharing`, `tenant-sharing`, `guests`, `sites-guests` | |
| `ownership` | `sites-owners`, `sites`, `groups` | `--minimum-owners N` |
| `app-exposure` | `applications`, `service-principals` | `--expires-within DAYS` |
| `ca-coverage` | `conditional-access` | `--policy-id ID` |

What holds for every one of them:

- **No resource is dropped.** A resource in the evidence is a row. Where the
  fact a scenario needs was not read, the row says `not-established` and why.
- **A refusal is never an empty answer.** A site that refused is not a closed
  site, a list that was refused is not an empty list, and a credential list
  that was not returned is not an application with none.
- **A relation is made on an identifier, and named.** Each inspection lists the
  relations it made and the ones it did not. Two facts side by side are not a
  relation.
- **A parameter is the operator's and is recorded.** The engine holds no view
  on how many administrators a site should have or how soon a credential
  should be renewed.
- **Time is the evidence's.** A credential is placed relative to when the
  evidence was collected, never to the clock.
- **Every inspection says what it did not establish**, and carries the digest
  of the evidence it read. `--out FILE` keeps it.

`m365g governance inspect-diff BEFORE AFTER` compares two inspections kept
with `--out`. Only the same scenario with the same parameters is compared. A
row that is gone has left the evidence; it is not said to have been deleted.

## Discovering what can be collected

`m365g collector list` shows every collector with the command that runs it
and whether it has read a directory. `m365g collector describe NAME` adds what
it reads, the permissions recorded for it, the rules it feeds and what its
proof did not cover. `m365g collector test NAME` is a contract test: it
holds the collector's packaged fixtures to the evidence contract and names each
with its origin, which is `synthetic`. Whether a directory has answered the
collector is printed on a separate line, from the proof registry, and the test
says it did not establish it. None of the three reaches a tenant.

Three states are reported apart and never added: a collector is
**contract-tested** when its behaviour is proved against a stand-in service,
and **tenant-verified** when the proof registry holds a record of a real read,
with what that read did not cover. A command is **published** when a released
version carries it.

## Output

`--output` says how a result is shown, and it is the same option on every
command that shows one: `text`, `json`, `csv` or `md`, as far as the command
has them.

- **A read answers in the terminal.** `m365g spo site list` prints what was
  read, as text unless `--output` says otherwise. The JSON view is the evidence
  documents themselves, untouched; CSV and Markdown are one row per resource
  with stable leading columns (`resource_type`, `name`, `url`, `native_id`,
  `tenant`, `collected_at`, `completed`, `unavailable`) followed by one column
  per fact, named `family.fact`: the path a rule uses for the same fact.
- **A view can be narrowed and ordered.** `--where column=value` shows the
  resources whose column prints that value, and `--sort column` orders them.
  The filter compares what the view prints, so a refusal is found as
  `--where site_guests.guests=[permission-denied]`. It never changes what was
  read or what `--evidence-out` keeps, and the command says how many resources
  it left out. A column nobody has is refused.
- **A view is not the evidence.** It is rendered from the documents the
  collection wrote and adds nothing to them. An observed fact is shown as what was observed.
  Any other state is shown as the state itself in square brackets, such as
  `[permission-denied]`, and never as a value: that is the one translation a
  view makes, and the contract value behind every cell is in the JSON view.
  Nothing is concluded. Without `--evidence-out` the
  documents are not kept, and the command says so on every run.
- **`--evidence-out DIRECTORY` keeps the evidence**: the documents, with their
  provenance and coverage, which is what rules evaluate.
- **Only the view is on stdout.** The collection's own report, progress and
  notes go to stderr, so `--output json` can be piped.

### The earlier spellings, which still work

| Earlier | Now | What happens to the earlier one |
|---|---|---|
| `collect SLICE --output DIRECTORY` | `--evidence-out DIRECTORY` | unchanged: evidence is written there and the earlier report is printed |
| `run --output DIRECTORY` | `run --evidence-out DIRECTORY` | unchanged |
| `--format F` on `connect`, `capabilities`, `run`, `evaluate`, `assess`, `report`, `diff` | `--output F` | unchanged; `md` is accepted for `markdown` |
| `run --out FILE`, `migration-read --out`, `contracts --out` | the same | unchanged: `--out` names a file or folder a command writes |

Precedence where a value could be read two ways: on `collect` and `run`,
`--output` followed by `text`, `json`, `csv`, `md`, `markdown` or `html` is a
format, and any other value is the evidence directory. A directory with one of
those names is written `./json`. A format given twice (`--format` and
`--output`), or a directory given twice (`--output DIRECTORY` and
`--evidence-out`), is refused with exit `2`.

