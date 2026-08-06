# Security

## What this tool can do to a tenant

Nothing. There is no write path: the collector calls no cmdlet that changes
anything, and CI proves it by parsing the script and failing on any mutating
verb. The engine reads evidence from disk and writes a report.

The worst outcome from running it is a report you disagree with.

## What it can read

Whatever the identity you sign in with can read. Both authentication modes are
delegated, so a run sees what one person sees, and every report states that on
its first page. Nothing is sent anywhere: the collector writes a file to your
disk and the engine reads it locally. There is no service on our side.

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
