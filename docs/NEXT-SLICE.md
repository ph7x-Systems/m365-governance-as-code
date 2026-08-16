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

---

# Recomputed 2026-08-16: what a collection reports while it runs

The table above scores rules and domains. This is neither, and it outranks all
three: it is a gap in what the engine can say about its own work.

## What `collect` cannot say today

```python
result = subprocess.run(argv, capture_output=True, text=True)   # collecting.py

@dataclass
class Outcome:
    slice_name, returncode, seconds, written, stdout, stderr

    @property
    def ok(self) -> bool:
        return self.returncode == 0
```

**Nothing until it ends.** `capture_output=True` buffers the child's output
until the process exits, so `collect sites` against a large tenant prints
nothing for however long it takes and then prints everything. The collector
does write progress, three lines of it including
`"321 sites enumerated by this identity"`, and none of it reaches the person
waiting.

**And `ok` is a boolean over an exit code.** A collection that reached two
hundred of three hundred sites and then lost its connection is `ok == False`,
which is the same answer as one that never authenticated. The first produced
evidence worth two hundred sites; the second produced nothing.

That is a collapse this engine does not make anywhere else. Coverage keeps
`requested` and `completed` apart and names the reason a fact was unavailable.
A rule answers `unknown` rather than failing when the gap could change its
answer. The collection outcome is the one place where a partial result and a
failure are the same value.

## What the slice adds

| State | Means |
|---|---|
| `completed` | Everything the slice asked for |
| `partial` | Usable evidence, incomplete coverage, with the reason |
| `failed` | No usable artefact |
| `cancelled` | Stopped deliberately, with a stated rule about what is kept |

And the child's output streams rather than being buffered, so a caller can
report what has been done while it is being done.

## Why this belongs to the engine

Every consumer wants it and none of them can derive it. A caller reading
`returncode` and guessing at partial from the number of files on disk is a
caller inventing governance meaning from a side effect, and the engine's whole
position is that nobody downstream should have to.

The CLI wants it first: `collect` is the one command with a duration, and today
it is silent for the whole of it.

## What this costs

**A contract version.** The state crosses the boundary in what the engine
publishes, so consumers re-vendor. That is a real cost and it is the correct
one: a collection state that lived only in a consumer would be that consumer's
opinion about an exit code.

## What must not change

Read only. The collector has no write path, CI proves it by parsing every file
in the tree on every release, and nothing here goes near that. Streaming what a
collector already prints is a change to how its output is carried, not to what
it is allowed to do.

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
