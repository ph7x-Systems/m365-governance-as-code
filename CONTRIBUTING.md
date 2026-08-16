# Contributing

Rules are the interesting contribution. The engine is small on purpose and
will stay that way; the value of this project is a growing set of checks whose
claims are honest about what kind of claim they are.

---

## Before you start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . && pip install -r requirements-dev.txt

./tools/release-check.sh     # everything CI runs, in the same order
```

That one script is the gate. It runs nine steps: dependencies, `ruff check`,
`ruff format --check`, `m365-governance validate`, the schemas, `pytest`,
coverage, `tools/examples.py --check`, and an evaluation of every fixture.

Run it before pushing. This list used to name four of the nine, so a pull
request could pass everything the document asked for and still be refused by
CI for formatting, which is a refusal nobody learns anything from.

The individual steps, when one of them is what you are working on:

```bash
ruff check src tools tests
ruff format --check src tools tests
m365-governance validate     # every rule, every layer
pytest                       # the suite
python tools/examples.py --check
coverage run -m pytest && coverage report
```

Coverage has a floor rather than a target. It moves up when something real
gets covered, and never down to accommodate a change that stopped testing
something.

All of it runs offline. No tenant is needed to contribute a rule.

---

## Writing a rule

Start from [rules/sharepoint/SPO-SITE-001.yaml](rules/sharepoint/SPO-SITE-001.yaml),
which is short, and read [docs/RULE-SCHEMA.md](docs/RULE-SCHEMA.md) once.

Three things decide whether a rule gets merged, and none of them is whether
we agree with it.

**The `basis` is honest.** Five kinds, and the source never decides the type.
An opinion that cites Microsoft documentation is still an opinion. If you
label a convention as a requirement, the pull request will be about that and
nothing else.

**`passes_without_resolving` is answered.** Every rule states, in writing, how
it can pass while the problem survives. It is a field of its own because it is
the one authors skip. If you cannot answer it, the rule is not understood well
enough yet, and that is a useful thing to discover before the review.

**The messages claim only what the rule established.** If the `fail` message
says "and still inherits its permissions", the rule has to have checked that.
The validator catches evidence declared and never consumed, which is where
this usually starts, but the sentence itself is on you.

The build fails, deliberately, when `basis` is missing, when a documented type
has no source, when a convention has no rationale, when the condition reads
evidence nobody declared, when evidence is declared and never consumed, when a
failure message interpolates a value that is missing precisely when that
message prints, when a YAML key is duplicated, when two rules share an id, or
when any unknown field appears anywhere.

That last one is `additionalProperties: false` everywhere. `severty: high`
must stop the build, not disappear.

---

## Reviewing a rule

[docs/review/RULE-REVIEW.md](docs/review/RULE-REVIEW.md) is the checklist, and
its criterion is worth repeating here:

> **The test is not agreement. It is disagreeing in the right place.**

Argue with the `basis` without mentioning the engine. Argue with the severity
without touching the condition. Name a missing limitation without asking to
see code. A review that opens with *"but how does the engine calculate this?"*
means the rule has not been written clearly enough yet.

---

## Changing an existing rule

Read [docs/CHANGE-POLICY.md](docs/CHANGE-POLICY.md). The test is one sentence:

> If a report produced yesterday would be interpreted differently today, the
> rule version must change.

Removing a limitation is a breaking change, and it is the one that looks like
it is not. A limitation is the boundary of the claim; deleting one widens the
claim without touching the condition.

---

## Collectors

A collector observes. It never returns `is_compliant`, `risk`, `score` or a
recommended action, because a collector that judges has moved the judgement
out of a reviewable diff and into code.

It never returns an empty list in place of an error, and never presents a
truncated response as a complete one. Those two are how this model fails in
practice, and neither looks like a decision when it is written: one is a
`catch` that returns `@()`, the other is a loop that stops at the first page.

Read-only, always. CI parses the PowerShell and fails on any mutating verb.

---

## Integrating with anything outside this repository

**Facts before design. Schema before mapping. Tenant before rule.**

Never implement external behaviour from memory, from a plausible-sounding
name, or from secondary documentation, when a schema, an enum, an assembly, an
API's own metadata or an official specification exists and can be inspected.

Before writing any integration:

1. **find the normative source** — the schema file, the loaded assembly, the
   published specification, not an article about it;
2. **enumerate the values it actually accepts**;
3. **record that discovery in a test**, under `tests/external/`, with the
   source and the date it was checked;
4. **only then write the mapping**;
5. **run it against real data** where that is possible at all.

If the normative source does not answer the question, **the product declares
the gap.** It does not fill it by plausibility.

This is not caution. It is the only pattern that has caught anything here:

| | |
|---|---|
| **PnP** | Microsoft removed the shared PnP Management Shell application on 9 September 2024, so callers now bring their own application registration — directly or through a supported configured default. This collector requires an explicit `-ClientId` because evidence has to name the application that observed it, and a value read from an ambient environment variable is one nobody can name afterwards. The claim this table used to make, "required since 2.99", cited a release that does not exist. |
| **SharePoint** | `SharingCapability` is not a property of a site. `Get-PnPSite -Includes` rejects it outright; it is a tenant property *about* a site. |
| **SharePoint** | `DefaultSharingLinkType: None` means "inherits the tenant", not "no default". The rule that read it as a value would have passed 53 sites knowing nothing. |
| **SARIF** | Asked in prose, a summary of the specification offered `redirect` and `hotspot` as permitted `result.kind` values. The schema's enum contains neither. |

The SARIF one is the cleanest illustration, because nothing about `redirect`
and `hotspot` looks wrong. **That they sound reasonable does not matter. That
they are absent from the enum ends the discussion.**

Recorded discoveries live in [tests/external/](tests/external/). A mapping
that uses a value absent from a recorded enum fails the build, and a recorded
fact with no source and no date fails it too: an unattributed fact is
indistinguishable from a remembered one.

---

## Licence and sign-off

**Inbound equals outbound.** Everything you contribute is licensed under the
same [MIT Licence](LICENSE) this project is released under. There is no
separate grant, and nothing you send is licensed to us on terms the rest of the
project does not already have.

**There is no CLA, and there will not be one.** A contributor licence agreement
asks you to assign or license rights beyond the project's own licence, usually
to a company. That would make this repository's licence and its contributors'
obligations two different things. Inbound=outbound keeps them one thing.

**Sign your commits off under the [DCO 1.1](DCO.txt).** The Developer
Certificate of Origin is a statement that you have the right to send what you
sent — not a transfer of anything. Add the line with `git commit -s`:

```
Signed-off-by: Your Name <your.email@example.com>
```

The name and address must be real and must be the ones you commit under. CI
refuses a pull request whose commits are not signed off, and it names the
commits rather than failing with a tick nobody can act on.

If you forget, `git rebase --signoff` from the merge base fixes a branch — the
refusal prints the exact command.

**History from before the policy is not reopened.** The rule applies to commits
a pull request introduces, measured from the merge base, and everything
reachable from the commit that adopted it is left alone. Rewriting published
history would change every hash on the default branch, break every link and
clone that refers to them, and re-certify years of work retroactively — which
is the opposite of what a certificate means.

**Nobody signs for anybody else.** A sign-off by someone other than the author
is a certificate about work the signer did not write, and the gate refuses it.
If a commit on your branch is not yours, its author adds the sign-off; a
maintainer will not add one on their behalf.

## Pull requests

One rule, or one coherent change, per pull request.

Say what kind of claim you are adding and why you classified it that way. That
sentence is the review.

Commit messages: what changed and why it matters, in prose, without a prefix
convention. If a commit needs a bullet list to be understood, it is probably
two commits.

---

## What we will decline

- automatic remediation, in any form, including a flag that only suggests it;
- a rule that executes code;
- inferring `basis` from the presence of a source;
- treating missing evidence as compliance, anywhere, for any reason.

Those four are the project. Everything else is open.
