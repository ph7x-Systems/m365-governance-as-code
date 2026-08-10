"""The generator's own rules about what it will and will not model.

These are about generated CODE rather than about a schema, which is why they
live apart from the schema tests: what is asserted here is that a consumer
receives a type for everything a document carries, and a named refusal for
everything the generator cannot honestly emit.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "src" / "m365_governance" / "data" / "generated" / "csharp"


def generator():
    """Load the generator as a module. It is a script, not a package."""
    spec = importlib.util.spec_from_file_location(
        "generate_models", ROOT / "tools" / "generate-models.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_citation_arrives_as_a_type_and_not_as_raw_json():
    """The one thing a generated model exists to stop.

    A run carries the rule's normative sources, and a consumer that received
    them as an opaque element would take the title and the url out of the JSON
    by hand — reimplementing part of the contract in a viewer, which is where
    the two quietly stop agreeing.
    """
    run = (GENERATED / "Run.g.cs").read_text(encoding="utf-8")

    assert 'JsonPropertyName("sources")] IReadOnlyList<Source>' in run
    assert "public sealed record Source(" in run
    for member in ("Url", "Title", "Publisher", "CheckedAt"):
        assert member in run, f"a citation without {member} is not one"


def test_the_adopted_shape_is_emitted_by_the_file_that_names_it():
    """Named and emitted in the same file, or it fails at the consumer.

    This is the defect the refusal was written for: `run` referenced the rule
    contract's `source`, `Source` was named, and no generated file defined it.
    It generated cleanly and broke a long way from here.
    """
    run = json.loads(
        (
            ROOT / "src" / "m365_governance" / "data" / "schemas" / "run.schema.json"
        ).read_text(encoding="utf-8")
    )
    ref = run["$defs"]["result"]["properties"]["sources"]["items"]["$ref"]
    assert "/rule/" in ref, "the citation is still defined by the rule contract"

    # The rule contract is not modelled, and that has not changed.
    module = generator()
    assert "rule.schema.json" not in module.GENERATE

    # Yet the type it names exists, in the file that names it.
    assert "public sealed record Source(" in (GENERATED / "Run.g.cs").read_text(
        encoding="utf-8"
    )


def test_a_shape_that_refers_on_is_refused_rather_than_half_emitted():
    """The bound on adoption, and the reason there is one.

    Everything resolves `#/$defs/...` against the document being rendered, so a
    def that refers on to further defs would resolve those names against the
    WRONG contract — silently, and into types that happen to exist. Refusing is
    the same rule as before, kept where it still applies.
    """
    module = generator()

    with pytest.raises(module.Unsupported) as refused:
        # `basis` is a real def in the rule contract and it refers on to
        # `source`, so it is exactly the case this bound exists for.
        module.adopt("rule", "basis", "result.basis", [])

    assert "refers on to other defs" in str(refused.value)
    assert "wrong contract" in str(refused.value)


def test_a_shape_that_is_not_there_is_named_rather_than_guessed():
    module = generator()

    with pytest.raises(module.Unsupported) as refused:
        module.adopt("rule", "not-a-def", "somewhere", [])

    assert "no $defs/not-a-def" in str(refused.value)


def test_a_schema_that_is_not_there_stops_the_run():
    module = generator()

    with pytest.raises(module.Unsupported) as refused:
        module.adopt("nothing-like-this", "source", "somewhere", [])

    assert "not modelled" in str(refused.value)
