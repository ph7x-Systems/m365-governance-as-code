# Agent inventory, against a tenant

Run on 2026-08-10 18:52 UTC, device login and read-only.
The site is not named here: this repository is public, and a URL is an identifier whether or not it is data.

## 1. What the module returns

0 agent(s) returned by `Get-PnPCopilotAgent` for this identity.

| Agent | Property | Present | Type |
|---|---|---|---|

## 2. What the collector recorded

| Agent | Type | Named | Instructions | Sources | by URL | by id |
|---|---|---|---|---|---|---|

Derived facts: count 0, total sources 0, agents declaring none 0.

No agent declares zero sources. **That is not proof the state is
impossible**: it is proof that nothing in this site reached it. Try
creating one with no source selected; if the interface refuses, that
refusal is the finding and is worth more than the fixture.

## 3. Agreement, field by field

No agents in this site, so the shape was not exercised. **Create one and run this again**: an empty result proves the call works and nothing about the model.

## 4. Fixture

No fixture: nothing was read, and a fixture built from nothing would be a shape somebody invented.

## 5. What happened after this run

Recorded by hand, because the script cannot see a browser.

`New` > `Agent` **was not offered on the site** this run read. That is what was
observed; **why** it was not offered is not established. Microsoft documents
several conditions that govern whether the option appears — licensing, the
per-user Copilot for SharePoint service plan, restricted content discovery on a
site, and file permissions — and this run distinguished none of them. Nothing
here says a licence is absent, because nothing here looked.

So the slice stops with the enumeration proven and the shape unproven:

| | |
|---|---|
| authentication | succeeded |
| connection to the site | succeeded |
| `Get-PnPCopilotAgent` | succeeded, not refused |
| agents returned | 0, for this site and this identity |
| agent object shape | **not exercised** |
| tenant-wide absence | **not established** — one site was read |
| the creation surface | not available on this site |
| why it was not available | **not established** |

An empty enumeration proves the call works and proves nothing about the model.
