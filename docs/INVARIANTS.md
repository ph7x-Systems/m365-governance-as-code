# The invariants, and what actually enforces each one

**A rule that only a person can keep is a rule that gets kept until somebody is
tired.** This lists every permanent property of this repository, what checks
it, and — where nothing does — says `UNENFORCED` rather than quietly dropping
the rule.

**The goal is to shrink the `UNENFORCED` column, never to shrink this table.**

| # | Invariant | Enforced by | What it caught |
|---|---|---|---|
| 1 | A published contract is immutable under the same version | `data/published-contracts.json` and `test_registry.py` compare the bytes of every version against the digest recorded when it was published | three contracts that had been edited under a published `$id` |
| 2 | A generated fixture is not a live observation | `capabilities --domains` publishes a live state per collector, and `test_capabilities.py` requires the state to come from the contract's enum | a collector publishing `live-validated` for a branch no real catalog had produced |
| 3 | How far validation went is declared, not described | `collector.validation` in `capability-manifest/1.3.0`, gated by `test_capabilities.py` | a comparison state claimed with no surface named |
| 4 | A coverage area is not both completed and unavailable | `test_collector.py` over every packaged document | a `null` entry that made the engine unable to open its own evidence |
| 5 | Every packaged document opens in the reader that reads evidence | `test_collector.py` runs the reader over every fixture | the same defect, in the branch no fixture covered |
| 6 | A published array is an array at every cardinality | `test_collector.py` exercises the fact builder at zero, one and many, comparing JSON type | a field that published a number for one period and an array for two |
| 7 | A capability is not proven until its canonical artefact crosses the integration boundary | `release-check.sh` installs the wheel into an empty environment and writes a bundle from outside any checkout; the consumer's own gate opens one | a bundle three samples wide, published because failures were skipped silently |
| 8 | Public documentation describes published behaviour only | the site's gate runs the declared version and compares every documented command against it | seven claims naming commands the published release did not carry |
| 9 | Every module exports what it declares, and every collector parses | `release-check.sh`, PSScriptAnalyzer, and an import check | a function left behind by a refactor |
| 10 | No evidence family disappears from the published bundle | `test_collector.py` reads the publisher's family list against the tree | a whole family invisible to consumers |
| 11 | Everything written is in English | `language-check.sh`, in the gate and in the pre-commit hook | comments in the wrong language, twice |
| 12 | Every commit carries a sign-off | `dco-check.sh` | — |
| 13 | The executor contract is not distributed | machine-local exclusion | — |
| 14 | `unknown` is never a pass | the rule model: every outcome is reachable and `unknown` is one of them, checked by `validate` | a rule returning `pass` from a catalog with nothing comparable |
| 15 | An observation and a governance conclusion are different claims | every rule declares a `basis`, checked by `validate` and by review | — |
| 16 | A search result does not establish that a population is empty | `population`, `acquisition_method` and `populations_not_observed` in the evidence contract | a count read as *this tenant has three*, when it was three files in one library |
| 17 | No layer publishes an aggregate score | `test_engine.py` refuses the field names an aggregate arrives under, and a rendered percentage in any produced document | a seven-figure total that summed quantities which are not commensurable |
| 18 | A presentation layer explains a contract value and never redefines it | **UNENFORCED.** Reviewed by reading | — |
| 19 | Live acquisition is separately authorized | **UNENFORCED IN THIS REPOSITORY.** The engine acquires no credential and refuses a sign-in against a directory nobody named, which is not the same thing as enforcing the rule | a session opened because a dependency had been installed |
| 20 | An absence carries a reason, and whose limitation it is | `test_collector.py` refuses a `detail` that restates the state, and requires an owner where `acquisition_attempts` records the area | — |
| 21 | Evidence is ranked | **UNENFORCED.** Reviewed by reading | — |
| 22 | A tool boundary is not an evidence boundary | **UNENFORCED.** Reviewed by reading | — |

## `UNENFORCED` is not one thing

**Three classes, and only the first creates implementation work.** Recorded so
that nobody reads the column and opens a card per row trying to reach zero.
**The goal is not zero unenforced. It is zero mechanisable invariants left
without a mechanism by accident.**

| Class | Meaning | Creates work |
|---|---|---|
| `mechanizable-gap` | we know roughly how to check it and have not | **yes** |
| `authority-boundary` | this software can constrain its own behaviour and cannot prove what a person was authorized to do | no |
| `review-boundary` | structure is checkable; the judgement inside it is not | no |

| # | Invariant | Class |
|---|---|---|
| 18 | A presentation layer explains and never redefines | `review-boundary` |
| 19 | Live acquisition is separately authorized | `authority-boundary` |
| 21 | Evidence is ranked | `review-boundary` |
| 22 | A tool boundary is not an evidence boundary | `review-boundary` |

**17 and 20 were `mechanizable-gap` and are now enforced**, with the smallest
gates that hold the existing invariant and without extending the evidence model
to do it. Neither needed a new field: what was missing was a check, not a
contract.

## What 19 actually enforces, and what it does not

**This engine does not enforce authorization and must not be described as
doing so.** Nothing inside a library can establish that the person who ran a
command had permission to run it.

What it does enforce, at its own boundary:

- it **acquires no credential**: an application registration is named, never
  created, and the command that would create one is printed for a person to run;
- it **writes nothing to a tenant**, and holds no write path under any flag;
- it **transmits no tenant evidence anywhere**, having no destination of its own;
- it **refuses to sign in against an address whose directory it could not
  resolve**, in every mode, so an interactive sign-in cannot land in an
  unrelated directory and report what it found there as an answer about the
  address that was typed;
- a certificate proceeds, because `-Tenant` names the directory explicitly.

**Everything past that is the operator's.** Enforcement of *who authorized this
run* belongs to whoever runs it, and a claim here that the product enforces it
would be a security property the product does not have.

## Why 18, 21 and 22 stay as review boundaries

A machine can check that a rule declares a `basis` and that the declaration is
one of the five kinds. **It cannot check that the basis is honest**, that the
evidence cited actually supports the claim, or that a limitation of one tool
was not quietly written down as a fact about Microsoft 365.

Structural preconditions are mechanised where they exist — every rule declares
a basis, every fact declares a state, every absence now declares a reason.
**Turning the judgement itself into a boolean to make this table green would be
the failure the table was written to prevent.**
