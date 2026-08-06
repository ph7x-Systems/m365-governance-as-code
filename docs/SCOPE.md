# Scope

> **This project evaluates the Microsoft 365 tenant that exists today. It does
> not infer the characteristics of an estate it has not observed.**

That sentence is the scope. Everything below is it, applied.

---

## Two modes

**Live** observes Microsoft 365 directly. A collector authenticates, reads,
and writes evidence. Everything it reports is something it saw.

**Assessment** evaluates evidence that came from somewhere else: an export
from a migration tool, an inventory somebody produced, a CSV. The engine
answers the same way, and the report says plainly that the completeness of
that evidence cannot be verified here.

```
Live                                    Assessment

  Microsoft 365                           ShareGate · SMAT · CSV
        │                                            │
   collector                                import adapter
        │                                            │
        └──────────────► evidence ◄─────────────────┘
                              │
                            engine
                              │
                            report
```

**The engine never knows which mode produced the evidence.** It reads a
document that matches the schema and applies rules to it. What differs is the
provenance the document carries, and what the report is therefore allowed to
say about it.

---

## What Live can answer

Questions that live inside Microsoft 365, because the facts behind them are in
Microsoft 365:

- who owns a site, and whether anybody does;
- where permission inheritance has been broken, and where it can no longer be;
- what is shared externally, and by which mechanism;
- how much of the estate is modern, classic, or somewhere between;
- what has not been touched in a long time.

None of that needs a legacy system to exist. All of it is a description of the
tenant as it is.

---

## What Live cannot answer, and will not pretend to

**Anything about a farm that is not here.** Whether a SharePoint Server
environment has full-trust solutions, how many content databases it has, what
its service applications look like: these are facts about a system this tool
has not connected to. A number produced without observing them would be a
guess wearing a report's clothes.

**Whether you should migrate, and to where.** That decision needs the estate
you are leaving, and Live has only the estate you are arriving at. It belongs
to Assessment, and only once the source inventory is in.

**Anything the identity could not read.** A delegated run sees what one person
sees. That is stated on the first line of every report it produces, and it is
not a formality: a report built from a partial view and read as a tenant-wide
statement is the most expensive mistake this tool can help somebody make.

---

## What Assessment adds

An import adapter turns a third-party export into evidence. It is a collector
like any other, and the same rules apply to it: it observes, it never judges,
and it never presents a truncated export as a complete one.

Imported evidence carries `identity_kind: imported` and an `import_source`
block naming the tool, its version, when the export was produced and by whom.
Every report built from it says:

> This assessment is based on imported evidence. Collection completeness
> cannot be verified by this engine.

That warning is not a disclaimer. It is a fact with consequences: we did not
choose the scope of that export, we do not know what the exporting identity
could read, and we cannot reproduce it. An `unknown` from a live run means
"collect it again". An `unknown` from an imported run may mean "ask whoever
ran the export".

---

## Why the separation matters

The alternative is a tool that answers every question, and answers some of
them from nothing.

A `destination` command that runs against a tenant with no source inventory
would have to infer the source. It would produce an answer, the answer would
be plausible, and nobody reading it could tell which parts were observed and
which were assumed. That is the failure this project is built against, in its
most tempting form: not a wrong answer, a confident one.

So the commands split by what they can see. Live commands do not accept a
destination question. Assessment commands do not run without imported
evidence. Neither borrows from the other.

---

## The Field Guide reads the same way

The [SharePoint Migration Field Guide](https://ph7x.com/guide/) puts it in the
same order, for the same reason: chapter 2 observes what is there, chapter 3
separates the facts that decide a destination from the facts that only price
it, and chapter 4 makes the recommendation. A recommendation made before the
observation is a preference with a document around it.

This tool is the observation, executable.
