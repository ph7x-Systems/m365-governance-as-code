"""Which contract a document belongs to, resolved offline and exactly.

THREE IDENTIFIERS, AND THEY ARE NOT INTERCHANGEABLE.

    dialect      `$schema` inside a schema document. Always
                 https://json-schema.org/draft/2020-12/schema
    contract     `$id` inside a schema document. The exact pH7x resource,
                 https://ph7x.com/schemas/m365-governance/evidence/2.0.0
    declaration  `$schema` inside an instance. The contract that instance
                 claims, and it must equal the owning `$id`

The third is an instance convention rather than a keyword. Inside a schema
document `$schema` names the dialect; inside a document of data it is an
ordinary property, and JSON Schema treats it as one. Using a single field for
two of these meanings is the confusion this module exists to prevent.

WHY NOT A SECOND VERSION FIELD. Every instance used to carry
`schema_version: "1.0"` while the schema validating it ended in `/1.2.0`. Two
representations of one thing, maintained by hand, in a pattern that could not
even express the other. `$schema` is declared `const` against the owning `$id`,
so disagreement is not a bug to catch — it is unrepresentable.

VALIDATION FOLLOWS THE DOCUMENT, NOT THE INSTALLATION. An archived assessment
is validated against the contract it declares, which may not be the newest one
this engine ships. A new version never reinterprets an old document: it is a
different contract, and turning one into the other is an explicit migration
that produces a new document rather than a re-reading of an old one.

NOTHING RESOLVES OVER THE NETWORK OR OFF THE FILESYSTEM. Every schema is loaded
into a registry up front, and a reference the registry does not hold is an
error rather than a fetch. A contract that could be satisfied from somewhere
else on the machine was never self-contained.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

#: The dialect every schema here is written in. A schema declaring another one
#: is not a version of ours, it is a different language.
DIALECT = "https://json-schema.org/draft/2020-12/schema"

#: `<name>/<major>.<minor>.<patch>`, and nothing else. No `latest`, no `v2`, no
#: floating alias: an archive resolved through a moving pointer is an archive
#: that changes meaning without anybody editing it.
CONTRACT = re.compile(
    r"^https://ph7x\.com/schemas/m365-governance/[a-z][a-z-]*/\d+\.\d+\.\d+$"
)


class RegistryError(Exception):
    """The registry cannot be built, or cannot answer."""


class UnknownContract(RegistryError):
    """A document claims a contract this registry does not hold."""


class Undeclared(RegistryError):
    """A document does not say which contract it claims."""


class SchemaRegistry:
    """Every contract this engine holds, keyed by its exact identity."""

    def __init__(self, entries: dict[str, tuple[Path, dict]]):
        self._entries = entries
        self._registry = Registry().with_resources(
            (uri, Resource.from_contents(document))
            for uri, (_path, document) in entries.items()
        )

    # -- building ---------------------------------------------------------

    @classmethod
    def load(cls, root: Path) -> SchemaRegistry:
        """Every `*.schema.json` under `root`, checked as it is registered.

        The checks are the registry. A map that accepted whatever it was given
        would move the problem to whoever reads it, one file at a time.
        """
        entries: dict[str, tuple[Path, dict]] = {}
        for path in sorted(root.rglob("*.schema.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RegistryError(f"{path}: not valid JSON: {exc}") from exc

            declared = document.get("$id")
            if not declared:
                raise RegistryError(f"{path}: no $id, so it identifies nothing")
            if document.get("$schema") != DIALECT:
                raise RegistryError(
                    f"{path}: dialect is {document.get('$schema')!r} and every "
                    f"contract here is written in {DIALECT}"
                )
            if not CONTRACT.match(declared):
                raise RegistryError(
                    f"{path}: {declared} is not an exact contract identity. "
                    "A version is three numbers; an alias that moves makes an "
                    "archive change meaning without anybody editing it"
                )
            if declared in entries:
                raise RegistryError(
                    f"{declared} is registered twice: {entries[declared][0]} "
                    f"and {path}. Two files claiming one identity means a "
                    "consumer resolves whichever was read first"
                )
            entries[declared] = (path, document)

        if not entries:
            raise RegistryError(f"{root}: no schemas, so the registry proves nothing")

        registry = cls(entries)
        registry._closure()
        return registry

    def _closure(self) -> None:
        """Every reference resolves, and everything registered is reachable.

        Both directions. A dangling reference makes a bundle unusable at the
        first document that follows it; an unreachable schema makes one that
        ships weight nobody can explain, and it is usually the leftover of a
        version somebody meant to delete.
        """
        referenced: set[str] = set()
        for path, document in (v for v in self._entries.values()):
            for ref in _refs(document):
                target = ref.split("#", 1)[0]
                if not target:
                    continue  # a local pointer, resolved within the document
                referenced.add(target)
                if target not in self._entries:
                    raise RegistryError(
                        f"{path} references {target}, which this registry does "
                        "not hold. The bundle is not self-contained"
                    )

        # Backwards, and it is narrower than it looks. A current schema sitting
        # at the top of the tree is a root somebody validates against, so being
        # referenced by nothing is normal. An archived one is unreferenced by
        # definition — that is what superseded means — and it has to say so by
        # living under `archive/`.
        #
        # What is left is a schema filed somewhere else that nothing points at,
        # which is how a half-finished version survives a rename and starts
        # answering questions nobody meant it to.
        root = _common_root(path for path, _ in self._entries.values())
        orphans = sorted(
            uri
            for uri, (path, _document) in self._entries.items()
            if uri not in referenced and path.parent != root and not _is_archived(path)
        )
        if orphans:
            raise RegistryError(
                "registered and reachable from nothing: " + ", ".join(orphans)
            )

    # -- answering --------------------------------------------------------

    def __contains__(self, contract: str) -> bool:
        return contract in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def contracts(self) -> list[str]:
        return sorted(self._entries)

    def schema(self, contract: str) -> dict:
        if contract not in self._entries:
            raise UnknownContract(
                f"{contract} is not a contract this engine holds. Known: "
                + ", ".join(self.contracts())
            )
        return self._entries[contract][1]

    def path(self, contract: str) -> Path:
        self.schema(contract)
        return self._entries[contract][0]

    def digest(self, contract: str) -> str:
        return hashlib.sha256(self.path(contract).read_bytes()).hexdigest()

    def validator(self, contract: str) -> jsonschema.Draft202012Validator:
        """A validator for one exact contract, resolving only what is held."""
        return jsonschema.Draft202012Validator(
            self.schema(contract), registry=self._registry
        )

    def validator_for(self, document: dict) -> jsonschema.Draft202012Validator:
        """The validator the **document** selects, never the newest installed.

        This is the whole point of the declaration. Choosing the current schema
        for an archived document would let a new version reinterpret an old
        one, quietly, and the reinterpretation would look like a finding.
        """
        declared = document.get("$schema")
        if not declared:
            raise Undeclared(
                "this document does not declare a contract, so nothing "
                "establishes what it should be read as. Documents written "
                "before the declaration existed are resolved by naming their "
                "contract explicitly"
            )
        return self.validator(declared)

    def problems(self, document: dict) -> list[str]:
        """What is wrong with a document, against the contract it claims."""
        validator = self.validator_for(document)
        return [
            f"{'/'.join(str(p) for p in error.path) or '<root>'}: {error.message}"
            for error in sorted(validator.iter_errors(document), key=str)
        ]

    def as_manifest(self) -> dict:
        """The registry as data: contract, path, digest.

        What a consumer vendors. Paths are relative to the schema root so the
        map means the same thing wherever the bundle is unpacked.
        """
        root = _common_root(path for path, _ in self._entries.values())
        return {
            contract: {
                "path": str(path.relative_to(root)),
                "digest": self.digest(contract),
            }
            for contract, (path, _document) in sorted(self._entries.items())
        }


def _refs(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_refs(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_refs(item))
    return found


def _is_archived(path: Path) -> bool:
    """A superseded version, kept so archived documents still resolve.

    Reachable from nothing on purpose: nothing current references it, and that
    is exactly what being superseded means.
    """
    return "archive" in path.parts


def _common_root(paths) -> Path:
    paths = list(paths)
    root = paths[0].parent
    while not all(str(p).startswith(str(root)) for p in paths):
        root = root.parent
    return root


def _no_network(_uri: str):
    raise NoSuchResource(ref=_uri)


def contract(name: str) -> str:
    """The exact contract a producer of `<name>` documents must declare.

    Read from the schema's own `$id` rather than written down again here. A
    constant beside it would be a third representation of the version, and the
    reason this module exists is that the second one drifted.
    """
    path = Path(__file__).resolve().parent / "data" / "schemas" / f"{name}.schema.json"
    if not path.is_file():
        raise UnknownContract(f"no packaged schema called {name}")
    declared = json.loads(path.read_text(encoding="utf-8")).get("$id", "")
    if not CONTRACT.match(declared):
        raise RegistryError(f"{path}: {declared!r} is not an exact contract identity")
    return declared
