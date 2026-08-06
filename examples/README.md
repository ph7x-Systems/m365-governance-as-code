# Examples

Every file here is the output of a real run against a fixture in this
repository. None is written by hand.

```bash
python tools/examples.py          # regenerate
python tools/examples.py --check  # fail if any is stale
```

CI runs the check. An example that drifts from the behaviour is worse than no
example: it stays plausible while the tool moves underneath it.

| File | Outcome | From |
|---|---|---|
| [pass.md](pass.md) | `pass` | a list inside the documented limit |
| [fail.md](fail.md) | `fail` | a list past 100,000 items, still inheriting |
| [unknown.md](unknown.md) | `unknown` | owners the identity could not read |
| [not-applicable.md](not-applicable.md) | `not-applicable` | a list that already has unique permissions |
| [invalid-evidence.md](invalid-evidence.md) | `invalid-evidence` | an item count that came back as a word |
| [bounded.md](bounded.md) | `pass`, from a bound | three owners and one unexpanded group |
| [report.json](report.json) | the JSON shape | the same bounded run |

There is no example of `error`. A rule cannot author one: it describes the
engine rather than the resource, so an example of it would be an example of a
bug.
