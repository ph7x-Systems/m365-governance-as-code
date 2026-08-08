# Next slice — the engine queue

**Recomputed 2026-08-08**, after the Sharing domain closed.

Engine-scoped candidates only. The product queue spans three repositories and
names work that is not public, so it lives with the platform contract rather
than here. This page says what the engine's own next steps are, and what it
refused.

Five factors, scored 0 to 3, **multiplied**. A zero anywhere eliminates the
candidate, which is how an unprovable one is refused arithmetically instead of
by argument. **Hard gates run before scoring**, and a candidate blocked by
missing evidence or by an owner-only boundary scores zero and is deferred with
its reason rather than offered as a choice.

| # | Candidate | Value | Impact | Ready | Conn. | Mat. | **Score** | Decision |
|---|---|---|---|---|---|---|---|---|
| 1 | Anyone link expiry at tenant level | 2 | 2 | **0** | 3 | 2 | **0** | deferred |
| 2 | `needs-tenant-validation`: enumeration completeness | 2 | 2 | 1 | 1 | 1 | 8 | owner-only |
| 3 | Open a second service | 3 | 3 | 1 | 1 | 2 | 18 | deferred |

**Nothing in the engine is currently executable at a score worth taking**, and
that is a result rather than a gap: SharePoint Online's seven domains all have
rules, collectors, fixtures and tests, and the three candidates above are each
blocked for a reason that is written down.

## 1 — Anyone link expiry

Microsoft recommends requiring expiry, and the only collectable value remains
an `Int32` whose `0` has no documented meaning. **A rule cannot distinguish
"expiry disabled" from any other special reading without inventing one**, and a
rule that guesses produces a finding somebody acts on.

Readiness 0, and the gap is exactly `0 semantics not documented`. The
collection path is not the obstacle: the `TenantSharing` mode already exists.
Full record in [COLLECTION-PATH-AUDIT.md](COLLECTION-PATH-AUDIT.md).

> **A closed domain may contain deferred candidates.** Sharing is closed on
> data. This does not hold it open and does not reopen it. It reopens when
> Microsoft documents the value, or a tenant observation settles it.

## 2 — enumeration completeness

Needs an interactive tenant run, which is owner-only and never a device-code
session. Not a blocker: no live rule depends on the answer.

## 3 — a second service

SharePoint Online is not finished, and three products at once, none of them
deep, is the failure mode the strategy names. High value and high impact do not
rescue low readiness, which is the arithmetic working as intended.

---

**The queue is recomputed, not followed.** Every completed cycle changes the
inputs, so this is regenerated from repository state rather than carried
forward.
