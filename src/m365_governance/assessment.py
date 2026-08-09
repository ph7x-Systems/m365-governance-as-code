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

#: Which members of `canonical` are hashed.
HASHED = ("run_set", "evidence", "versions", "manifest")

#: The two manifest fields left out of the manifest's own digest.
#:
#: `assessment_id` is the id, and the id derives from that digest: including it
#: would ask the identity to contain itself.
#:
#: `label` is what a person calls it, and renaming something is not producing a
#: different thing. Including it would give the same evaluation a new identity
#: because somebody typed a better name, and every earlier reference to it
#: would stop resolving.
#:
#: THE FIRST VERSION LEFT THE WHOLE MANIFEST OUT, and a test found what that
#: cost: `tenant`, `created_at` and `identity_kind` could all be changed
#: without anything noticing, so an assessment could be relabelled as
#: belonging to a different tenant and still verify. Those three are facts
#: about what was assessed. A label is not, and the difference is the line.
NOT_IN_ITS_OWN_DIGEST = ("assessment_id", "label")


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


def _hashable(value: Any, name: str) -> Any:
    """The part as it is hashed. Only the manifest differs from itself."""
    if name != "manifest":
        return value
    return {k: v for k, v in value.items() if k not in NOT_IN_ITS_OWN_DIGEST}


#: What a collector may declare about the identity that observed something.
#: `imported` is the third kind: facts from a tool we did not write, whose
#: collection completeness this engine cannot verify.
IDENTITY_KINDS = ("delegated", "application", "imported")


class Mismatch(ValueError):
    """The manifest would have said something the evidence does not support."""


def _one_tenant(evidence: list[dict]) -> str:
    """Which tenant this evidence is about, or a refusal.

    An assessment is about one tenant. Two tenants in one archive is not a
    bigger assessment, it is two assessments in a trench coat: every count in
    the summary would be a sum across estates nobody manages together.
    """
    seen = {
        document.get("provenance", {}).get("tenant_id")
        for document in evidence
        if document.get("provenance", {}).get("tenant_id")
    }
    if not seen:
        raise Mismatch(
            "no evidence document says which tenant it is about, so the "
            "assessment cannot say either"
        )
    if len(seen) > 1:
        raise Mismatch(
            "this evidence is about more than one tenant "
            f"({', '.join(sorted(seen))}), and an assessment is about one"
        )
    return seen.pop()


def _identity(evidence: list[dict]) -> str:
    """Which kind of identity observed this, across the whole set.

    `mixed` is a real answer and never a reassuring one. It says the documents
    do not agree, which the reader must resolve per document rather than take
    as an average: an application run and a delegated run in one archive mean
    part of it is tenant-wide and part of it is one person's view.
    """
    seen = {
        document.get("provenance", {}).get("identity_kind")
        for document in evidence
        if document.get("provenance", {}).get("identity_kind")
    }
    if not seen:
        raise Mismatch(
            "no evidence document says which identity observed it, and "
            "without that an empty result cannot be read"
        )
    unknown = seen - set(IDENTITY_KINDS)
    if unknown:
        raise Mismatch(
            f"identity_kind is one of {IDENTITY_KINDS}, not {sorted(unknown)}"
        )
    return seen.pop() if len(seen) == 1 else "mixed"


def _evaluated_from(run_set: RunSet, evidence: list[dict]) -> None:
    """Refuse a run set that was not evaluated from this evidence.

    Nothing structural stops a caller passing one tenant's runs and another
    collection's documents, and the result would verify perfectly: the digests
    prove nothing moved after the fact, not that the two halves ever belonged
    together. Every finding would then cite evidence that never produced it.
    """
    documented = {
        document.get("resource", {}).get("id")
        for document in evidence
        if document.get("resource", {}).get("id")
    }
    orphans = sorted(
        str(run.resource.get("id"))
        for run in run_set.runs
        if run.resource.get("id") not in documented
    )
    if orphans:
        raise Mismatch(
            "the run set evaluated resources this evidence does not contain: "
            + ", ".join(orphans[:3])
            + (f" and {len(orphans) - 3} more" if len(orphans) > 3 else "")
        )


def build(
    run_set: RunSet,
    evidence: list[dict],
    *,
    engine_version: str,
    created_at: str,
    tenant: str | None = None,
    identity_kind: str | None = None,
    label: str | None = None,
) -> dict:
    """One assessment, with its identity derived rather than assigned.

    `created_at` is passed in rather than read from the clock, so that the same
    inputs produce the same bytes. An assessment whose digest moved because
    time passed would be unverifiable by construction.

    `tenant` and `identity_kind` are **read from the evidence**, not accepted
    from the caller. They used to be two free strings, which meant the manifest
    could describe a tenant that appears nowhere in the documents underneath
    it, and the digests would happily prove that lie unchanged. Passing either
    one now asserts it: agreement is silence, disagreement is a refusal.
    """
    observed_tenant = _one_tenant(evidence)
    if tenant is not None and tenant != observed_tenant:
        raise Mismatch(
            f"the manifest would say {tenant!r} and the evidence was collected "
            f"from {observed_tenant!r}"
        )

    observed_identity = _identity(evidence)
    if identity_kind is not None and identity_kind != observed_identity:
        raise Mismatch(
            f"the manifest would say {identity_kind!r} and the evidence was "
            f"observed by a {observed_identity!r} identity"
        )

    _evaluated_from(run_set, evidence)
    tenant, identity_kind = observed_tenant, observed_identity

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

    manifest = {
        "created_at": created_at,
        "tenant": tenant,
        "identity_kind": identity_kind,
    }
    if label:
        manifest["label"] = label
    canonical["manifest"] = manifest

    parts = {name: _digest(_hashable(canonical[name], name)) for name in HASHED}
    combined = hashlib.sha256(
        "".join(f"{name}:{parts[name]}" for name in sorted(parts)).encode()
    ).hexdigest()

    # Derived, not chosen. An id somebody picked would let two different
    # assessments claim to be one, and two exports of the same one disagree.
    manifest["assessment_id"] = combined
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
        actual = _digest(_hashable(canonical[name], name))
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
