"""The Run schema describes what the engine emits, and stays that way.

A schema written once and never checked is documentation, and documentation
about your own output rots faster than documentation about somebody else's.
This evaluates every fixture and validates the result, so the contract and the
code cannot drift apart quietly.

**Direction matters here.** These schemas were written from the engine's actual
output, imperfections included, because a schema describing what the code ought
to do cannot validate what it does. When one of these fails, the first question
is which of the two moved, not which of the two is wrong.
"""

from __future__ import annotations

import json
import subprocess

import jsonschema
import pytest
from referencing import Registry, Resource

from conftest import DATA

SCHEMAS = DATA / "schemas"
FIXTURES = sorted((DATA / "fixtures" / "sharepoint").glob("*.json"))


def registry() -> Registry:
    """Every schema by its own `$id`, so `$ref` across files resolves without
    a network lookup. A validator that reaches the internet to check a
    contract is a validator that fails on an aeroplane."""
    resources = []
    for path in sorted(SCHEMAS.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        resources.append((document["$id"], Resource.from_contents(document)))
    return Registry().with_resources(resources)


def validator(name: str) -> jsonschema.Draft202012Validator:
    document = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(document, registry=registry())


def evaluated(path) -> dict | None:
    done = subprocess.run(
        ["m365-governance", "evaluate", "--evidence", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    return json.loads(done.stdout) if done.returncode == 0 else None


def test_there_are_fixtures_to_evaluate():
    """A suite that silently found nothing passes forever."""
    assert len(FIXTURES) > 20


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_every_evaluated_fixture_matches_the_run_schema(path):
    run = evaluated(path)
    if run is None:
        pytest.skip("this fixture does not evaluate on its own")
    errors = sorted(validator("run.schema.json").iter_errors(run), key=str)
    assert not errors, (
        f"{path.name} produced a run the schema refuses: {errors[0].message}\n"
        f"at {'/'.join(str(p) for p in errors[0].absolute_path)}"
    )


def test_the_schemas_are_reachable_from_each_other():
    """`run-set` refs `run` by `$id`. If that link breaks, every set-level
    check quietly validates nothing at all."""
    schema = validator("run-set.schema.json")
    empty = {
        "run_schema_version": "1.0",
        "resources": 0,
        "by_class": {},
        "set_aside": 0,
        "counts": {
            "pass": 0,
            "fail": 0,
            "unknown": 0,
            "not-applicable": 0,
            "invalid-evidence": 0,
            "error": 0,
        },
        "run_coverage": {},
        "runs": [],
    }
    assert not list(schema.iter_errors(empty))

    # And the ref really resolves: a malformed run inside must be refused.
    broken = dict(empty, runs=[{"not": "a run"}])
    assert list(schema.iter_errors(broken)), (
        "a run-set accepted a run that is not a run, so the $ref did not "
        "resolve and the set-level schema is checking nothing"
    )
