# Security

## What this tool can do to a tenant

Nothing. There is no write path: the collector calls no cmdlet that changes
anything, and CI proves it by parsing the script and failing on any mutating
verb. The engine reads evidence from disk and writes a report.

The worst outcome from running it is a report you disagree with.

## What it can read

Whatever the identity it authenticated as can read, and there is more than one
kind of identity. Every report names which one produced the evidence.

<!-- identity-modes:start -->

| Identity | How it authenticates | What it can read |
|---|---|---|
| `delegated` | a person signs in, interactively or with a device code | what that one person can see. Nothing a run produces this way is a tenant-wide statement |
| `application` | a registered application authenticates itself with a certificate | whatever the tenant granted the application. It is bounded by no person's view |
| `not-established` | the evidence does not record it | unknown. This is the case where what a report could reach cannot be bounded at all |

<!-- identity-modes:end -->

The table above is derived from `identity_kind` in the published `connection`
contract and checked against it by a test. The paragraphs around it are written
by people.

**Read-only by design is not least privilege, and the two are often confused.**
There is no write path, so nothing this tool does can change a tenant — that is
the first section of this document and it holds for every identity. How much a
run can READ is a separate question, answered by the identity somebody
configured. An application with broad read permissions produces a report with
broad reach, and it is still read-only.

Nothing is sent anywhere: the collector writes a file to your disk and the
engine reads it locally. There is no service on our side.

## Evidence files contain tenant data

The JSON a collector produces names sites, lists and principals. Treat it as
you would any inventory export. The repository's `.gitignore` excludes
`evidence/` and `*.tenant.json` so that a real run does not end up in a commit
by accident, and the fixtures here are fabricated on purpose.

## Reporting a vulnerability

Email **support@ph7x.com**. Please include what you ran, what happened, and
what you expected.

We will confirm receipt, and we would rather hear about a suspected problem
than not. If a report turns out to be a misunderstanding, that is useful too:
it usually means the documentation is wrong.

Please do not open a public issue for anything that would let somebody read
data they should not.

## Scope

In scope: the collector, the engine, the schemas, and anything in this
repository that could cause a wrong conclusion to look like a right one.

Out of scope: the security of Microsoft 365 itself, and the correctness of a
governance decision somebody makes after reading a report.
