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
#: cost: `tenant`, `created_at` and the identity summary could all be changed
#: without anything noticing, so an assessment could be relabelled as
#: belonging to a different tenant and still verify. Those are facts about what
#: was assessed. A label is not, and the difference is the line.
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


#: Which authentication identity observed something. `not-established` belongs
#: here because it is a real answer about identity: the evidence did not say.
#:
#: `imported` used to sit in this list and does not belong in it. It answers how
#: the evidence arrived, not who observed it, and putting the two in one field
#: meant an import could never also say that a delegated identity collected it.
IDENTITY_KINDS = ("application", "delegated", "not-established")

#: How the evidence reached the engine. Orthogonal to identity, and separate
#: for the same reason the states above are: an imported document that names
#: its collecting identity has both answers, and one field could only hold one.
ACQUISITION_KINDS = ("collected", "imported")


class Mismatch(ValueError):
    """The manifest would have said something the evidence does not support."""


def _one_tenant(evidence: list[dict]) -> dict:
    """Which tenant this evidence is about, or a refusal.

    An assessment is about one tenant. Two tenants in one archive is not a
    bigger assessment, it is two assessments in a trench coat: every count in
    the summary would be a sum across estates nobody manages together.

    A TENANT IS NOT A HOSTNAME. It has one directory identity and any number of
    addresses: the admin centre, the primary host, every multi-geo satellite.
    So the id decides when it is present, and the host decides only while no id
    has been observed — which is today, because no collection path for the
    directory id has been proven on a tenant.

    A multi-geo satellite therefore still reads as a second tenant here, and
    that is deliberate. Folding two hosts together on the strength of a shared
    prefix would be inventing an identity nobody read. The refusal is explicit
    and says what is missing.
    """
    tenants = [
        document.get("provenance", {}).get("tenant") or {} for document in evidence
    ]
    ids = {t.get("id") for t in tenants if t.get("id")}
    hosts = {t.get("host") for t in tenants if t.get("host")}

    if not ids and not hosts:
        raise Mismatch(
            "no evidence document says which tenant it is about, so the "
            "assessment cannot say either"
        )
    if len(ids) > 1:
        raise Mismatch(
            "this evidence carries more than one directory identity "
            f"({', '.join(sorted(ids))}), and an assessment is about one tenant"
        )
    if not ids and len(hosts) > 1:
        raise Mismatch(
            f"this evidence is about more than one host ({', '.join(sorted(hosts))}) "
            "and none of it carries a directory identity, so nothing establishes "
            "that they are one tenant. If they are, collect the directory id"
        )
    if len(hosts) > 1:
        # One directory identity and several hosts is the multi-geo case
        # answered properly: the id settles it and the hosts are addresses.
        # Which host to record is then a choice, so it is not made — the id is
        # the identity and the host is dropped to the one the id was read with.
        hosts = {sorted(hosts)[0]}

    return {"id": sorted(ids)[0] if ids else None, "host": sorted(hosts)[0]}


def _summarise(evidence: list[dict], field: str, vocabulary: tuple[str, ...]) -> dict:
    """What the whole set says about one provenance field.

    A summary and not a value. The manifest used to hold an identity kind and
    answer `mixed` when the documents disagreed, which is not an identity
    anybody can authenticate as: it is a statement about a collection of
    documents wearing the name of a statement about one.
    """
    seen = {
        document.get("provenance", {}).get(field)
        for document in evidence
        if document.get("provenance", {}).get(field)
    }
    unknown = seen - set(vocabulary)
    if unknown:
        raise Mismatch(f"{field} is one of {vocabulary}, not {sorted(unknown)}")

    kinds = sorted(seen)
    if not kinds:
        raise Mismatch(
            f"no evidence document declares its {field}, and the manifest may "
            "not summarise what nothing states"
        )
    if kinds == ["not-established"]:
        return {"summary": "not-established", "kinds": []}
    return {"summary": "single" if len(kinds) == 1 else "multiple", "kinds": kinds}


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
    label: str | None = None,
) -> dict:
    """One assessment, with its identity derived rather than assigned.

    `created_at` is passed in rather than read from the clock, so that the same
    inputs produce the same bytes. An assessment whose digest moved because
    time passed would be unverifiable by construction.

    The tenant, the identity summary and the acquisition summary are **read
    from the evidence**, not accepted from the caller. The first two used to be
    free strings, which meant the manifest could describe a tenant that appears
    nowhere in the documents underneath it, and the digests would happily prove
    that lie unchanged. `tenant` may still be passed, and passing it asserts
    it: agreement is silence, disagreement is a refusal.
    """
    observed_tenant = _one_tenant(evidence)
    if tenant is not None and tenant not in (
        observed_tenant["id"],
        observed_tenant["host"],
    ):
        raise Mismatch(
            f"the manifest would say {tenant!r} and the evidence was collected "
            f"from {observed_tenant['host']!r}"
        )

    identity = _summarise(evidence, "identity_kind", IDENTITY_KINDS)
    acquisition = _summarise(evidence, "acquisition", ACQUISITION_KINDS)
    _evaluated_from(run_set, evidence)

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
        "tenant": observed_tenant,
        "identity": identity,
        "acquisition": acquisition,
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
