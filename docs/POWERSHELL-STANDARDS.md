# PowerShell engineering standard

**One file defines the standard. Many small modules implement it.**

This document is the whole policy. Nothing here is repeated in a `.ps1`
header, because a standard that lives in nine file headers is nine standards.

It applies to every PowerShell file in this repository — today that is the
SharePoint Online collector and the modules it loads.

---

## The rule that outranks the rest

> **Collectors observe. Rules decide. PowerShell must not contain governance
> judgement.**

PowerShell reads facts. YAML interprets them. Python evaluates and reports.
A threshold, a recommendation, a severity or the word *compliant* inside a
`.ps1` moves a decision out of a reviewable diff and into code that nobody
diffs, and the whole model collapses into a script with opinions.

This is enforced, not asked for: `test_the_collector_returns_no_conclusion`
fails on the field names that presume a rule.

---

## What Microsoft documents, and what we decided

The project's rules carry a `basis` saying whether they rest on a
documented requirement, documented guidance, or a convention of ours. A
standard for our own code deserves the same honesty, so each line below says
which it is. **A convention is not weaker; it is differently accountable.**
Guidance can be checked against a page. A convention can only be checked
against a reason, so the reason is written next to it.

### Documented by Microsoft

| Rule | Source |
|---|---|
| Functions are named `Verb-Noun`, using a verb from `Get-Verb` | [Approved Verbs](https://learn.microsoft.com/powershell/scripting/developer/cmdlet/approved-verbs-for-windows-powershell-commands) |
| Never a synonym of an approved verb — `Remove`, never `Delete` or `Eliminate` | same page, recommendation 3 |
| Never an inflected form — `Get`, never `Getting` or `Gets` | same page, recommendation 4 |
| Pascal case for function and parameter names | [Strongly Encouraged Guidelines, SD02](https://learn.microsoft.com/powershell/scripting/developer/cmdlet/strongly-encouraged-development-guidelines) |
| Nouns are specific rather than generic | Strongly Encouraged Guidelines, SD01 |
| `Write-Host` is for display only; data goes to the pipeline | [Write-Host](https://learn.microsoft.com/powershell/module/microsoft.powershell.utility/write-host): *"produce for-(host)-display-only output … By contrast, to output data to the pipeline, use `Write-Output` or implicit output."* |
| A module states what it exports | [about_Module_Manifests](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_module_manifests): *"For performance and discoverability, you should always explicitly list the functions you want your module to export … without using any wildcards."* |
| `Export-ModuleMember` even when it restates the default | [Export-ModuleMember](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/export-modulemember): *"optional, but it is a best practice. Even if the command confirms the default values, it demonstrates the intention of the module author."* |

All four pages checked on 8 August 2026.

### Our conventions, with the reason attached

| Rule | Why it is ours and not Microsoft's |
|---|---|
| PowerShell 7.4 or later | The collector is invoked as `pwsh` by `collecting.py` and has never been tested on Windows PowerShell 5.1. Stating a floor we test is honest; claiming 5.1 compatibility we have never exercised is not. |
| `Set-StrictMode -Version Latest` in every file | A property that does not exist returns `$null` silently, and a `$null` that reaches an evidence envelope is indistinguishable from an observed absence. Strict mode turns a typo into an error instead of into a fact. |
| `$ErrorActionPreference = 'Stop'` at the top | Non-terminating errors let a collector continue past a failed read and emit a document that looks complete. A failure has to be a failure. |
| `[CmdletBinding()]` on every function | Buys `-Verbose` and `-ErrorAction` uniformly, so diagnosing a tenant run does not depend on which functions happened to be written carefully. |
| Every parameter typed, every mandatory one declared | An untyped `$SiteUrl` accepts an array and produces an envelope about nothing. |
| No `catch { }` that swallows | A swallowed error becomes a missing fact with no reason, and a fact with no reason is the one thing the evidence model refuses. Catch, and record **why**, in the `detail`. |
| No credentials, tenants or site URLs in code | They are parameters. A collector that knows one tenant is a script, not a product. |
| Timestamps ISO 8601 with an offset | Two runs from two timezones must be comparable without knowing where either was run. |
| Collections always emitted as arrays | PowerShell unrolls a single-element collection to a scalar. JSON that is sometimes an object and sometimes a list breaks the schema on the day a tenant happens to have exactly one of something. |
| `null`, `0`, `false` and *missing* are four different answers | The distinction the whole product rests on. `0` is a measurement; missing is an admission. See [COLLECTION-PATH-AUDIT.md](COLLECTION-PATH-AUDIT.md) for the case where the difference was undecidable and the rule was therefore not written. |
| Every fact carries its provenance | The `raw` block names the cmdlet property the value came from, so a reader can go and check. |
| No default value ever recorded as `observed` | The audit above exists because a cmdlet can return a default that looks exactly like a measurement. |
| No write cmdlet, ever | Enforced twice: a regex over the source, and an AST walk of every command name in the tree. |

### Deliberate divergence

`Get-SharingFacts`, `Get-OwnerFacts` and their siblings use a **plural** noun,
against SD01's *"the noun … should be singular"*. They return the complete set
of facts for one resource, not one fact, and `Get-SharingFact` would describe
something the function does not do. The guidance exists so that users can
predict a command name; these are internal functions with no user. Recorded
here rather than quietly ignored.

---

## Layout

The entry point orchestrates. It does not collect.

```text
collectors/powershell/sharepoint/
  Get-SpoEvidence.ps1        entry point: parameters, connect, dispatch, write
  modules/
    Evidence.psm1            fact shapes, envelope, provenance, failure states
    Connection.psm1          authenticating, and nothing else
    Sites.psm1               tenant inventory
    Sharing.psm1             one site, and the organisation
    Permissions.psm1         owners, lists, inheritance
    Modernity.psm1           template, branding, publishing
    Activity.psm1            when a person last changed something
    Classification.psm1      labels and what a site records about its content
    Spfx.psm1                app catalog and pages
```

The entry point reads, end to end:

```text
connect → select slice → call one collector function → emit JSON
```

**Every module imports `Evidence.psm1` by path, explicitly.** Command lookup
inside a module falls back to the global session state, so an implicit import
would appear to work and would break the day a module is imported on its own
in a test. Explicit is deterministic; deterministic is testable.

`Evidence.psm1` imports nothing. It is the bottom of the stack, and a cycle
through it would be a design error rather than an inconvenience.

---

## What the release contract proves

Modularising removes a proof unless the gates move with it. Both read-only
checks originally named **one file path**; against a tree they would have gone
on passing while proving nothing about nine tenths of the code. The gates walk
the directory:

| Gate | What it establishes |
|---|---|
| `Parser::ParseFile` on every file | It is analysable PowerShell, not text that happens to be in a `.ps1` |
| AST command-name walk over the tree | No command in any file begins with a mutating verb on the PnP, Graph or SPO surface |
| Regex over every file | The same claim by a second, independent method |
| Module import test | Every `.psm1` loads standalone and exports exactly what it declares |
| Approved-verb test | Every exported function's verb is in `Get-Verb` |
| Every entry-point call resolves | No function is called that no module defines — the failure mode a refactor produces |
| PSScriptAnalyzer | The rules nobody remembers |
| `test_the_collector_returns_no_conclusion` | No governance judgement in PowerShell |

**None of this runs anything against a tenant, and none of it can.** A function
can parse cleanly, export correctly, pass every walk here, and throw on its
first line against a real tenant. These are a floor under review, not a
substitute for it, and the tenant findings recorded in
the live-validation matrix are what actual validation looks like.

### PSScriptAnalyzer

Required when the collector gates run. Install it with:

```powershell
Install-Module PSScriptAnalyzer -Scope CurrentUser
```

Configured by [`PSScriptAnalyzerSettings.psd1`](../PSScriptAnalyzerSettings.psd1)
at the repository root. Suppressions live in that file with a comment saying
why, never as an attribute buried in a function.

---

## Adding a module

1. Read the cmdlet reference for every property first. The project's standing
   rule is that a property is not evidence until the collection path is proven
   to populate it.
2. One responsibility. If the file needs the word *and* to describe it, it is
   two files.
3. Import `Evidence.psm1` by path; export with `Export-ModuleMember`.
4. Every fact through the `Evidence.psm1` constructors, so provenance and
   failure states cannot be forgotten.
5. Add the module to the wheel's payload count if the release contract asserts
   it, and run the contract.
6. **A collection path that no rule can consume does not ship.** The twin of
   rule 1, and it has already reverted one attempt.
