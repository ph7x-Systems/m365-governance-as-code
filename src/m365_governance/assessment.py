"""Assemble an Assessment: what a person means by "I assessed a tenant".

Nobody says they have a RunSet. A RunSet is the evaluation; an Assessment is
the thing somebody archives, exports, sends and opens later, and it cannot be
handed over unless it carries what produced it.

TWO HALVES, AND THE SPLIT IS THE POINT.

    canonical   the manifest, the run set, the evidence it was evaluated from,
                the versions of engine, rules and collectors, and the digests
    derived     reports, each naming what rendered it

Only the canonical half is hashed, because the other one is rebuilt rather
than trusted. A report that cannot be regenerated from the canonical half is a
second original, not a projection.

THE EVIDENCE IS KEPT WHOLE. A finding whose evidence was discarded cannot be
re-checked, and re-checking is the entire point of recording evidence at all.

NO DIFF LIVES HERE. A diff is a claim about two assessments, so it belongs to
a Comparison. Inside one, it would make a single state assert something about
another, which is how a convenience becomes canonical truth.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .results import RunSet

SCHEMA_VERSION = "1.0"

#: Which members of `canonical` are hashed. `manifest` is excluded because it
#: carries the `assessment_id`, and that id derives from these digests: hashing
#: it here would ask the identity to contain itself.
HASHED = ("run_set", "evidence", "versions")


def _digest(value: Any) -> str:
    """A digest of the value in the contract's canonical form.

    THE CANONICAL FORM IS PART OF THE CONTRACT, not an implementation detail,
    because a consumer has to reproduce it exactly to verify anything:

        keys sorted, byte order
        no whitespace between tokens
        UTF-8, with nothing escaped that does not have to be

    That last line was learned rather than chosen. The first version left
    Python's default `ensure_ascii=True` in place, and a consumer using the
    ordinary .NET encoder escaped apostrophes as \u0027 while Python wrote
    them raw. Ten apostrophes in one run set were enough for two correct
    implementations of "the same JSON" to produce different digests.

    Escaping as little as possible is the only version of this that two
    languages agree on without one of them imitating the other's defaults.
    """
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build(
    run_set: RunSet,
    evidence: list[dict],
    *,
    engine_version: str,
    tenant: str,
    identity_kind: str,
    created_at: str,
    label: str | None = None,
) -> dict:
    """One assessment, with its identity derived rather than assigned.

    `created_at` is passed in rather than read from the clock, so that the same
    inputs produce the same bytes. An assessment whose digest moved because
    time passed would be unverifiable by construction.
    """
    if identity_kind not in ("delegated", "application"):
        raise ValueError(
            f"identity_kind is delegated or application, not {identity_kind!r}"
        )

    # Rule and collector versions come from what was actually evaluated, never
    # from what is installed now. Two releases later, "the rule changed" has to
    # be answerable, and only the run knows which version answered.
    rules: dict[str, str] = {}
    collectors: dict[str, str] = {}
    for run in run_set.runs:
        for result in run.results:
            rules[result.rule_id] = result.rule_version
        collector = run.provenance.get("collector")
        if collector:
            collectors[collector] = run.provenance.get("collector_version", "unknown")

    canonical: dict[str, Any] = {
        "run_set": run_set.to_dict(),
        "evidence": evidence,
        "versions": {
            "engine": engine_version,
            "rules": dict(sorted(rules.items())),
            "collectors": dict(sorted(collectors.items())),
        },
    }

    parts = {name: _digest(canonical[name]) for name in HASHED}
    combined = hashlib.sha256(
        "".join(f"{name}:{parts[name]}" for name in sorted(parts)).encode()
    ).hexdigest()

    manifest = {
        # Derived, not chosen. An id somebody picked would let two different
        # assessments claim to be one, and two exports of the same one disagree.
        "assessment_id": combined,
        "created_at": created_at,
        "tenant": tenant,
        "identity_kind": identity_kind,
    }
    if label:
        manifest["label"] = label

    canonical["manifest"] = manifest
    canonical["hashes"] = {
        "algorithm": "sha256",
        "canonical_parts": parts,
        "canonical_hash": combined,
    }

    return {"schema_version": SCHEMA_VERSION, "canonical": canonical}


def verify(assessment: dict) -> list[str]:
    """What is wrong with this assessment, or an empty list.

    Separate from `build` on purpose: verifying is what a consumer does to
    something that arrived, and it must not need the code that made it.
    """
    problems: list[str] = []
    canonical = assessment.get("canonical", {})
    hashes = canonical.get("hashes", {})
    stored = hashes.get("canonical_parts", {})

    for name in HASHED:
        if name not in canonical:
            problems.append(f"canonical is missing {name}")
            continue
        actual = _digest(canonical[name])
        if stored.get(name) != actual:
            problems.append(f"{name} does not match its digest")

    combined = hashlib.sha256(
        "".join(f"{n}:{d}" for n, d in sorted(stored.items())).encode()
    ).hexdigest()
    if hashes.get("canonical_hash") != combined:
        problems.append("the canonical hash does not cover the parts it lists")

    declared = canonical.get("manifest", {}).get("assessment_id")
    if declared != hashes.get("canonical_hash"):
        problems.append(
            "the assessment id is not the canonical hash, so the identity was "
            "assigned rather than derived"
        )
    return problems
