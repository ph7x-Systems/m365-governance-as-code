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
| 17 | No layer publishes an aggregate score | **UNENFORCED.** Reviewed by reading | a seven-figure total that summed quantities which are not commensurable |
| 18 | A presentation layer explains a contract value and never redefines it | **UNENFORCED.** Reviewed by reading | — |
| 19 | Live acquisition is separately authorized | **UNENFORCED IN THIS REPOSITORY.** The engine acquires no credential and refuses a sign-in against a directory nobody named, which is not the same thing as enforcing the rule | a session opened because a dependency had been installed |
| 20 | `not established` is a conclusion, not an early stop | **UNENFORCED.** The states exist in prose; nothing requires an absence to carry the surfaces attempted | — |
| 21 | Evidence is ranked | **UNENFORCED.** Reviewed by reading | — |
| 22 | A tool boundary is not an evidence boundary | **UNENFORCED.** Reviewed by reading | — |

## The four that matter most, and why they are still unenforced

**17 and 20 are mechanisable and are not mechanised yet.** An aggregate over
unlike observations could be refused where evidence is assembled, and an
absence could be required to carry `surfaces_attempted`, `surfaces_unavailable`
and the ownership of the limitation, the way `acquisition_attempts` already
does for one family. Both are gaps, not decisions.

**19 cannot be fully enforced from inside a library.** Nothing here can stop
the operator of a shell from running a command. What this repository can do, it
does: it acquires no credential, writes nothing to a tenant, transmits no
evidence, and refuses to sign in against an address whose directory it could
not resolve. **Enforcement beyond that belongs to whoever runs it**, and
claiming otherwise would put a security property in the product that the
product does not have.

**21 and 22 are judgements about how a claim was reached.** A machine can check
that a rule declares a basis; it cannot check that the basis is honest.
Recording them as unenforced is the accurate answer, and deleting them because
no gate exists would be the failure this file was written to prevent.
