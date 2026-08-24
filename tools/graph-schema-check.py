#!/usr/bin/env python3
"""Settle every Graph claim in the register against the service's own schema.

A REFERENCE PAGE AND A SCHEMA ANSWER DIFFERENT QUESTIONS. The page says what an
endpoint is for and which permission reads it; only `$metadata` says whether the
thing exists in the version being claimed. `evidence-surfaces.json` ranks the
machine-readable contract above the prose, and this is that rank applied to the
one file where a wrong API version is most expensive: the register that decides
what gets built next. A row recorded as `v1.0` that turns out to be beta is a
dependency somebody would otherwise discover after writing the collector.

NO TENANT, NO IDENTITY, NO CONSENT. Both metadata documents are served
anonymously and describe the service, not any tenant. Nothing here authenticates,
and nothing here may be extended to a call that does.

OFFLINE IS `not established`, NEVER A PASS. If the documents cannot be fetched
the check says so and exits non-zero on `--check`. A verification that quietly
succeeds when it could not run is worse than no verification, because the row
keeps its claim and gains a tick.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / "src" / "m365_governance" / "data" / "candidate-surfaces.json"
METADATA = "https://graph.microsoft.com/{version}/$metadata"
VERSIONS = ("v1.0", "beta")


class Unreachable(Exception):
    """The schema could not be read, so nothing was established either way."""


def metadata(version: str, timeout: int) -> str:
    try:
        with urllib.request.urlopen(METADATA.format(version=version), timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise Unreachable(f"{version}: {exc}") from exc


def rows(register: dict) -> list[dict]:
    return [s for s in register["surfaces"] if s.get("schema_name")]


def check(surface: dict, schemas: dict[str, str]) -> tuple[bool, str]:
    """Is the surface where the register says it is, and only there?

    `Name="x"` rather than a path: the metadata declares entity types, singletons
    and navigation properties by name, and a name absent from a document cannot
    be reached by any path in that version.
    """
    needle = f'Name="{surface["schema_name"]}"'
    found = [v for v in VERSIONS if needle in schemas[v]]
    claimed = surface["schema_check"]["present_in"]
    if found == claimed:
        return True, ", ".join(found)
    if not found:
        return False, "in neither v1.0 nor beta"
    return False, f'recorded as {", ".join(claimed)} and found in {", ".join(found)}'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero when a row disagrees with the schema, "
                         "or when the schema could not be read at all")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    register = json.loads(REGISTER.read_text())
    try:
        schemas = {v: metadata(v, args.timeout) for v in VERSIONS}
    except Unreachable as exc:
        print(f"not established -- the Graph schema could not be read ({exc}).")
        print("No row was verified and none was refuted.")
        return 1 if args.check else 0

    bad = 0
    for surface in rows(register):
        ok, detail = check(surface, schemas)
        mark = "✓" if ok else "✗"
        print(f"  {mark} {surface['id']:<44} {detail}")
        bad += not ok
    print()
    print(f"{len(rows(register))} recorded Graph surfaces, {bad} disagreeing with the schema")
    return 1 if (bad and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
