# Fixtures

Every test in this repository runs against these files and never against a
tenant. A test that needs a tenant is a test that does not run.

## They preserve the shape, not the data

**No evidence from a real tenant enters this repository.** `.gitignore`
refuses `evidence/` and `*.tenant.json`. Every file here is written by hand,
from a real run that was then deleted.

Keep from the real run:

| | |
|---|---|
| **Collection states** | `observed`, `missing`, `not-supported`, `permission-denied`, `partial`, `invalid` — in the combinations a tenant actually produced. A combination nobody has seen is a combination nobody has tested a rule against. |
| **The product's own error text** | *Attempted to perform an unauthorized operation* is what six of 53 sites returned. A report is rendered around messages like that one, and inventing a friendlier one tests the wrong thing. |
| **The structure of the facts block** | Field for field, including the `raw.field` that names the property the collector read. |

Fabricate, always:

| | |
|---|---|
| **URLs and tenant names** | `contoso.sharepoint.com`. Never a real host. |
| **GUIDs** | Group ids, label ids, anything that resolves to something in somebody's directory. |
| **Dates, display names, titles** | And anything a person or an organisation could be recognised from. |

The rule is one sentence: **a fixture must be able to reproduce a defect
without being able to identify anybody.**

A fixture that needs real data to be meaningful is describing a gap in the
schema, not a limitation of the fixture. Say so in an issue rather than
pasting a tenant into a pull request.

## Naming

`<resource>-<slice>-<case>.json`, where the case names the state rather than
the outcome: `site-class-label-unresolved`, not `site-class-fails-002`. A
fixture named after an outcome has to be renamed the first time a rule
changes, and by then it usually is not.

## Adding one

A new fixture exists to reach a state no existing fixture reaches. Before
adding it, check the outcome matrix for the rules that read the same facts:
if every outcome is already reachable, the new file is a duplicate with a
different site name in it.

Every fixture is evaluated in CI, so a document that no longer matches the
evidence schema fails the build rather than sitting here being wrong.
