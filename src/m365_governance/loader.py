"""Layer 1: the file is a document at all.

Duplicate YAML keys are the reason this layer exists. Most parsers accept them
and keep the last, which in a governance rule means one `severity` silently
overriding another. No later layer can see what was lost, so it has to be
rejected here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


class DocumentError(Exception):
    """The file is not a document. Nothing downstream may run."""


@dataclass(frozen=True)
class LoadedRule:
    path: Path
    data: dict


@dataclass(frozen=True)
class LoadedEvidence:
    path: Path
    data: dict


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate keys instead of keeping the last."""


def _no_duplicates(loader: _StrictLoader, node, deep: bool = False) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise DocumentError(
                f"duplicate key {key!r} at line {mark.line + 1}, column "
                f"{mark.column + 1}. One value silently replaced another."
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates
)


def load_yaml(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise DocumentError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DocumentError(f"{path}: expected a mapping at the top level")
    return data


def load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise DocumentError(f"{path}: not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DocumentError(f"{path}: expected an object at the top level")
    return data


def load_rule(path: Path) -> LoadedRule:
    return LoadedRule(path=path, data=load_yaml(path))


def load_rules(directory: Path) -> list[LoadedRule]:
    """Every rule under a directory, ordered by path so runs are reproducible."""
    if not directory.is_dir():
        raise DocumentError(f"{directory}: not a directory")
    return [load_rule(p) for p in sorted(directory.rglob("*.yaml"))]


def load_evidence(path: Path) -> LoadedEvidence:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return LoadedEvidence(path=path, data=load_yaml(path))
    return LoadedEvidence(path=path, data=load_json(path))


def load_profile(path: Path) -> dict:
    return load_yaml(path)
