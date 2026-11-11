# The command line

**Owner decision, 2026-11-11.** The command line is regrouped so that a person
can sign in once and then work by commands, in the manner of other Microsoft
365 command lines, without changing what the engine establishes: evidence,
provenance, schemas, exit codes and the first-run contract stay as they are.
This file owns the shape of the command line. `docs/FIRST-RUN-CONTRACT.md`
owns the journey; the two do not restate each other.

## What may never break

The surface published before the regrouping is frozen in
`tests/frozen/cli-v1-surface.json` and held by
`tests/test_cli_compatibility.py`: nineteen commands, every option each took,
every value an option accepted, both executable names (`m365g` and
`m365-governance`, charter `D87`), and the meaning of the exit codes — `0` a
result, `1` a negative result, `2` a refusal. Consumers invoke this engine as a
subprocess by those names. A new name is an addition and never a replacement.
