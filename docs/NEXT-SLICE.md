# Next slice — the calculation

**Computed 2026-08-08, after the Sharing domain closed.**

This is the executor's priority calculation, written down so it can be
disagreed with. A calculation that only happened in a reply cannot be.

Five factors, scored 0–3, **multiplied**. Multiplication is the point: a zero
anywhere eliminates the candidate, which is how half a capability gets refused
arithmetically instead of by argument.

| # | Candidate | Value | Impact | Ready | Conn. | Mat. | **Score** | Decision |
|---|---|---|---|---|---|---|---|---|
| 1 | Site-side chain for the tenant sharing facts — Knowledge, Guide, Compass, graph | 2 | 2 | 3 | 3 | 2 | **72** | **chosen** |
| 2 | Tenant rule on *whether* Anyone links expire at all | 2 | 2 | 3 | 3 | 2 | **72** | next |
| 3 | `SharingDomainRestrictionMode` / `PreventExternalUsersFromResharing` rules | 2 | 2 | 3 | 2 | 1 | 24 | rejected |
| 4 | `needs-tenant-validation`: enumeration completeness | 2 | 2 | 1 | 1 | 1 | 8 | owner-only |
| 5 | A rule on `site.sharing_capability` | 2 | 1 | 0 | 1 | 1 | **0** | blocked |
| 6 | Open a second service | 3 | 3 | 1 | 1 | 2 | 18 | deferred |

## Why the winner won a tie

Candidates 1 and 2 both score 72. Tie-break rule 3 decides it: **close a
domain rather than open one.** Candidate 1 finishes a slice that is already
half-built; candidate 2 starts a new one. Three half-domains is the failure
mode the strategy names, and the contract's clause 8 says a slice is complete
only when every affected layer is coherent. The Governance half of Sharing
shipped; the Knowledge, Guide, Compass and graph half did not.

Candidate 2 is second and not deferred: it is the same domain, its evidence
path already exists, and it is expected to run immediately after.

## Why the losers lost

**3 — the other tenant sharing settings.** `SharingDomainRestrictionMode` is
described by Microsoft and not recommended; `PreventExternalUsersFromResharing`
likewise. A rule on either would carry `convention` while looking like
guidance. Maturity 1 because a convention with product impact is the owner's
decision, not the executor's. **Rejected, not deferred:** nothing will change
this except the owner deciding, so leaving it in the queue would be pretending
otherwise.

**4 — enumeration completeness.** Readiness 1: it needs an interactive tenant
run, which is owner-only and never a device-code session. Not a blocker for
anything shipping — no live rule depends on the answer.

**5 — a rule on `site.sharing_capability`.** Readiness **0**, so the product is
zero and the arithmetic eliminates it without argument. The property comes from
the enumeration path whose completeness candidate 4 exists to settle. The safe
value for the same question already exists at `sharing.capability`, and
`SPO-SHARE-001` uses it.

**6 — a second service.** Readiness 1: SharePoint Online is not finished, and
the strategy is explicit that three products at once, none of them deep, is
the failure mode. High value and high impact do not rescue a low readiness,
which is the arithmetic working as intended.

## What the next calculation will look like different

Every completed cycle changes the inputs. After candidate 1 ships, its
connectivity contribution is spent; after candidate 2 ships, the Sharing
domain has nothing above 24 left, and the queue moves to whichever domain
scores highest on a repository that no longer looks like this one.

**The queue is recomputed, not followed.**
