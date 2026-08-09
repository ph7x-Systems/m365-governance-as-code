#!/usr/bin/env python3
"""Generate the consumer models from the schemas the engine owns.

    tools/generate-models.py            write the models
    tools/generate-models.py --check    fail if what is on disk is stale

WHY THIS EXISTS. A consumer that writes its models by hand against JSON this
engine happens to emit has a synchronisation problem waiting for the first
schema change, and the synchronisation is invisible until something silently
reads a field that moved.

WHAT THIS GENERATOR DOES NOT KNOW. Who consumes it. The engine publishes
contracts and a generator; naming a particular consumer here would make the
public repository depend on knowing about a private one, and the next consumer
would arrive to find the generator shaped around somebody else.

WHAT "GENERATED" HAS TO MEAN, AND IT IS NOT "produced automatically". It means
verifiable equivalence with the contract. A class that compiles against a
schema it no longer matches is worse than a hand-written one, because nobody
re-reads generated code.

**THE PART A CLASS CANNOT CARRY.** Measured rather than assumed: the six
schemas use `if`/`then`/`else`, `allOf`, `anyOf`, `not` and `const`, and no C#
type expresses any of them. `Comparison` requires `factors` only when
`attribution.state` is `established`; a record cannot say that.

    the model    carries the SHAPE, and refuses unknown members
    the schema   carries every constraint a shape cannot express
    a consumer   validates AND deserialises. Neither alone is the contract.

So each generated file states, in its own header, which constraints it does
not enforce. A developer reading the DTO learns what it cannot promise, rather
than assuming a type check was a contract check.

UNSUPPORTED CONSTRUCTS FAIL. A construct this generator does not understand
stops it, named, rather than being dropped into a weaker model. Silence there
would produce a type that looks complete and is not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src" / "m365_governance" / "data" / "schemas"
OUT = ROOT / "src" / "m365_governance" / "data" / "generated" / "csharp"

#: Pinned. A generator whose version floats produces output that changes
#: without the contract changing, and the diff then means nothing.
GENERATOR_VERSION = "1.0.0"

#: The contract as a whole. Moves when any schema moves, so a consumer can say
#: which contract it was built against in one string rather than by comparing
#: six digests by eye.
CONTRACT_VERSION = "1.0.0"

#: The aggregates a consumer imports. Evidence and rule schemas describe this
#: engine's INPUTS, which no external consumer constructs, so generating them
#: would ship types nobody builds.
GENERATE = (
    "run.schema.json",
    "run-set.schema.json",
    "assessment.schema.json",
    "comparison.schema.json",
)

#: Constructs that decide the SHAPE. The generator handles these.
SHAPE = {
    "type",
    "properties",
    "items",
    "$ref",
    "required",
    "enum",
    "$defs",
    "$schema",
    "$id",
    "title",
    "description",
    "additionalProperties",
    "minimum",
    "minLength",
    "minItems",
    "uniqueItems",
    "pattern",
    "format",
}

#: Constructs that constrain VALUES. No C# type expresses them, so they are
#: reported in the generated header instead of being silently lost.
CONSTRAINT = {"if", "then", "else", "allOf", "anyOf", "oneOf", "not", "const"}

PRIMITIVE = {
    "string": "string",
    "integer": "int",
    "number": "double",
    "boolean": "bool",
}


class Unsupported(Exception):
    """A construct the generator does not understand. Never downgraded."""


def pascal(name: str) -> str:
    """Upper-case the first letter of each part and leave the rest alone.

    `.capitalize()` lower-cases everything after the first letter, which turned
    `ChangeAttribution` into `Changeattribution`. Generated code that looks
    almost right is the worst kind.
    """
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", name) if p]
    return "".join(p[0].upper() + p[1:] for p in parts)


def constraints_in(node, found: set[str]) -> set[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CONSTRAINT:
                found.add(key)
            constraints_in(value, found)
    elif isinstance(node, list):
        for item in node:
            constraints_in(item, found)
    return found


def unknown_in(node, found: set[str]) -> set[str]:
    """Anything that is neither shape nor a known constraint stops the run."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in SHAPE and key not in CONSTRAINT and not key.startswith("_"):
                found.add(key)
            if key in ("properties", "$defs"):
                for sub in value.values():
                    unknown_in(sub, found)
            else:
                unknown_in(value, found)
    elif isinstance(node, list):
        for item in node:
            unknown_in(item, found)
    return found


def type_of(node: dict, name: str, nested: list, defs: dict | None = None) -> str:
    """The C# type for one property, queuing nested records as it goes."""
    if "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/$defs/"):
            target = ref.rsplit("/", 1)[1]
            # A `$ref` to a def that is not an object is not a record. `outcome`
            # is a nullable enum of strings, and naming a type for it produced a
            # reference to something the file never defined.
            resolved = (defs or {}).get(target, {})
            if "properties" not in resolved:
                return type_of(resolved, name, nested, defs)
            return pascal(target)
        # A cross-file `$ref` names a type the sibling file defines. Two forms,
        # and the first was being parsed as if it were the second, which
        # produced a type called `Defs`.
        #
        #   .../run/1.0.0#/$defs/counts   ->  Counts
        #   .../run/1.0.0                 ->  Run
        #
        # They resolve because every generated file shares one namespace, so a
        # `$defs` type defined once is visible to all of them.
        url, _, fragment = ref.partition("#")
        if fragment.startswith("/$defs/"):
            return pascal(fragment.rsplit("/", 1)[1])
        return pascal(url.rstrip("/").rsplit("/", 2)[-2])

    if "oneOf" in node:
        branches = [b for b in node["oneOf"] if b.get("type") != "null"]
        if len(branches) == 1:
            inner = type_of(branches[0], name, nested, defs)
            return inner if inner.endswith("?") else inner + "?"

    declared = node.get("type")
    if isinstance(declared, list):
        # ["string", "null"] is the only union that reaches here.
        others = [t for t in declared if t != "null"]
        if len(others) != 1:
            raise Unsupported(f"{name}: union of {declared}")
        return PRIMITIVE.get(others[0], "JsonElement") + "?"

    if declared == "array":
        inner = type_of(node.get("items", {}), name + "Item", nested, defs)
        return f"IReadOnlyList<{inner}>"

    if declared == "object":
        if "properties" in node:
            nested.append((pascal(name), node))
            return pascal(name)
        return "JsonElement"

    if declared in PRIMITIVE:
        return PRIMITIVE[declared]

    # No `type` at all: any JSON value, which the evidence model needs for a
    # fact whose value can be a number, a string, a list or nothing.
    return "JsonElement?"


def record(name: str, node: dict, nested: list, defs: dict | None = None) -> str:
    required = set(node.get("required", []))
    lines = [f"public sealed record {name}("]
    members = []
    for prop, schema in node.get("properties", {}).items():
        kind = type_of(schema, name + pascal(prop), nested, defs)
        if prop not in required and not kind.endswith("?"):
            kind += "?"
        doc = schema.get("description", "")
        members.append((prop, kind, doc))
    for i, (prop, kind, doc) in enumerate(members):
        comma = "," if i < len(members) - 1 else ""
        if doc:
            lines.append(f"    /// <summary>{doc.replace('<', '&lt;')}</summary>")
        lines.append(
            f'    [property: JsonPropertyName("{prop}")] {kind} {pascal(prop)}{comma}'
        )
    lines.append(");")
    return "\n".join(lines)


def render(path: Path) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))

    unknown = unknown_in(document, set())
    if unknown:
        raise Unsupported(
            f"{path.name}: {sorted(unknown)} are neither shape nor known "
            "constraints. Teach the generator or change the schema; do not "
            "let a weaker model through."
        )

    not_enforced = sorted(constraints_in(document, set()))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    title = pascal(document.get("title", path.stem))

    defs = document.get("$defs", {})
    pending: list = [(title, document)]
    for def_name, def_node in defs.items():
        if "properties" in def_node:
            pending.append((pascal(def_name), def_node))

    # ONE queue, drained until empty. Two passes let a `$defs` entry ask for a
    # nested type after the nested queue had already run dry, and the type it
    # asked for was never emitted: the file compiled in my head and not in the
    # compiler.
    body, seen = [], set()
    while pending:
        name, node = pending.pop(0)
        if name in seen:
            continue
        seen.add(name)
        body.append(record(name, node, pending, defs))

    warning = (
        "\n".join(f"//   {c}" for c in not_enforced)
        if not_enforced
        else "//   none: every constraint in this schema is a shape this type carries"
    )

    return f"""// <auto-generated>
// From {path.name}, by tools/generate-models.py {GENERATOR_VERSION}.
// Schema sha256: {digest}
//
// DO NOT EDIT. Run the generator; a hand-edited file stops being generated
// and starts being a second, quieter contract.
//
// THIS TYPE CARRIES THE SHAPE AND NOT THE RULES. The schema uses constructs
// that no C# type expresses, so deserialising successfully is not the same as
// honouring the contract:
{warning}
//
// VALIDATE AGAINST THE SCHEMA AS WELL. Two settings are required and are not
// the defaults:
//
//   UnmappedMemberHandling = Disallow          unknown members are ignored
//                                              by default; these schemas
//                                              refuse them
//   RespectRequiredConstructorParameters = true a missing required member is
//                                              filled with null by default
//
// Both were verified against a compiler rather than assumed, and even with
// both the model is narrower than the contract. Demonstrated: a property that
// is optional and NOT nullable, such as an optional `string`, permits absence
// and refuses null. C# collapses the two into the same `null`, so
//
//   {{"tenant": null}}   the model accepts it, the schema refuses it
//
// Deserialising successfully is therefore not honouring the contract, and the
// order that holds is validate, then deserialise.
// </auto-generated>
#nullable enable
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Ph7x.Governance.Contracts;

{chr(10).join(body)}
"""


def build_manifest() -> dict:
    """What a consumer needs in order to know which contract it holds.

    A digest per schema and one over the set, so a bundle can be verified
    without the engine being anywhere near the machine. That last part is the
    whole point: a guard that only works when the sibling checkout happens to
    exist is a guard that is absent on the machine that builds the release.
    """
    schemas = {}
    for path in sorted(SCHEMAS.glob("*.json")):
        schemas[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    combined = hashlib.sha256(
        "".join(f"{name}:{digest}" for name, digest in sorted(schemas.items())).encode()
    ).hexdigest()
    return {
        "_comment": [
            "The contract this engine publishes. Copied into a consumer beside",
            "the schemas and the generated models, so the consumer can prove",
            "locally which contract it was built against.",
            "",
            "Refreshing it is an explicit operation. A consumer that compared",
            "itself opportunistically against whatever engine happened to be on",
            "the machine would be reproducible only on that machine.",
        ],
        "contract_version": CONTRACT_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generated": sorted(
            pascal(n.replace(".schema.json", "")) + ".g.cs" for n in GENERATE
        ),
        "schemas": schemas,
        "set_digest": combined,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for name in GENERATE:
        path = SCHEMAS / name
        try:
            text = render(path)
        except Unsupported as refused:
            print(f"  ✗ {refused}")
            return 1
        target = OUT / (pascal(name.replace(".schema.json", "")) + ".g.cs")
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != text:
                stale.append(target.name)
        else:
            target.write_text(text, encoding="utf-8")
            print(f"  wrote {target.relative_to(ROOT)}")

    manifest = build_manifest()
    manifest_path = OUT.parent / "manifest.json"
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not manifest_path.is_file() or (
            manifest_path.read_text(encoding="utf-8") != manifest_text
        ):
            stale.append(manifest_path.name)
    else:
        manifest_path.write_text(manifest_text, encoding="utf-8")
        print(f"  wrote {manifest_path.relative_to(ROOT)}")

    if args.check:
        if stale:
            print(f"  ✗ stale: {', '.join(stale)} — run tools/generate-models.py")
            return 1
        print(f"  ✓ {len(GENERATE)} models current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
