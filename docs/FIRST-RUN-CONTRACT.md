# The first-run contract

**Owner decision, 2026-08-20.** This repository owns the journey a person takes
from an empty machine to their first report, and owns it as an executable
contract rather than as prose. The README, the website and the desktop product
consume this file. None of them restates it.

## Why it is here and not in the documentation

The journey was the only thing in this programme that crossed all three
repositories and had no owner. Every technical contract has one — the schemas,
the outcomes, the basis vocabulary, the exit codes — and each is respected. The
journey fragmented instead, into a README, a manual, a knowledge base and a
CLI, and the four drifted apart in the ordinary way: nobody was wrong, and
nobody was responsible.

An audit on 2026-08-20 measured the drift. Application authentication was
recorded as unimplemented in the README, documented as working in the manual,
implemented for `collect`, and accepted-then-ignored by `connect`. The manual
published three command pages declaring a version in which those commands do
not exist. The exit-code contract was published by one repository and violated
by another, and no gate in either could see the disagreement.

**The reason it was invisible is that documentation cannot fail.** This
repository already knows what to do about a claim nobody can check: it makes it
declare its basis and it verifies it against the artefact. That machine was
never pointed at the product's own front door. This file points it there.

## The eight steps

The journey is these steps, in this order. A step is defined by the question it
answers, and it belongs to this contract whether or not a command exists for it
yet.

| | Step | The question it answers | Surface |
|---|---|---|---|
| 1 | **Prerequisites** | What must exist on this machine before anything runs? | `doctor` |
| 2 | **Identity** | Which application registration will observe the tenant, and where does it come from? | `setup` |
| 3 | **Authentication** | Can this identity sign in? | `connect` |
| 4 | **Authorization** | Can this identity *read what the rules need*? | `connect` |
| 5 | **Target** | Which tenant, which sites, and where is that recorded? | `setup`, project file |
| 6 | **Run** | One command from a configured target to evidence and a result | `run` |
| 7 | **Assessment** | The document somebody else can check without us | `assess` |
| 8 | **Report** | The thing a person reads and acts on | `report` |

**Steps 3 and 4 are two steps and not one.** `Connect-PnPOnline` succeeds with
zero permissions granted. A product that reports "connected" after step 3 has
verified authentication and reported authorization, which is the same class of
error as rendering `unknown` as a pass: it answers a question nobody asked with
a word the reader will take for the answer to the one they did.

## What the contract requires of each step

**Nothing interactive or remote begins before the local refusals are spent.**
An input that can be rejected from its shape is rejected before a process is
started, a browser is opened or a network is reached. The engine already holds
this rule for authentication modes; it applies to every input.

**A refusal is exit `2` and a negative result is exit `1`.** A path that is not
there, an argument that is missing and a document that is not what the command
expects are refusals: nothing was read, so nothing was decided. This is
published in the exit-code reference, and it is the contract a pipeline reads.

**Every failure carries a reason a machine can act on.** A verdict that only a
person can interpret forces every consumer to parse English or invent its own
vocabulary, and inventing one is the second authority this programme exists to
remove. Where a step can fail in ways that lead a reader somewhere different,
the difference is in the contract, not only in the prose beside it.

**No step requires a concept from a later step.** The vocabulary this engine
uses to describe its own work — slices, evidence documents, profiles, run sets
— is the product once a report exists. Before one exists it is architecture,
and requiring it in order to obtain a first result is the tool asking to be
understood before it agrees to be useful.

**A step that needs something the user does not have says how to obtain it.**
Naming what is missing is half a diagnosis. `doctor` already does the whole of
it for one dependency and half of it for another; the standard is the whole of
it, everywhere.

## What consumes this, and how

- **`README.md`** orders its opening by these steps and links here for the
  definition. It does not restate them.
- **The website manual** documents each step against a published release, and a
  gate proves the commands and options it names exist in the version its pages
  declare. Documentation of unreleased work is not published as documentation
  of a release.
- **The desktop product** presents these steps and no others: environment,
  identity, connection, access check, scope, assessment, findings. Where this
  contract has no reason for a failure, the interface does not invent one.

## What this contract does not decide

It does not decide what a rule may conclude, what evidence means, or what any
outcome is worth. Those are owned by the schemas and by the trust model, and
nothing here may be read as changing them. This contract is about reaching the
point where they begin to apply.
