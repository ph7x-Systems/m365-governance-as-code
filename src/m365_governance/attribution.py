"""From a finding back to the observation that supports it, mechanically.

`docs/ATTRIBUTION.md` names the defect class and states the one relation that
has to survive composition: **a fact block, and the document that supplied it.**
This walks it, in the direction a reader asks the question.

    finding
      -> result.evidence_used[].path        "permissions.unique_scope_count"
      -> the first segment of that path     "permissions"
      -> attribution[fact block]            the document that supplied it
      -> that document's provenance         the acquisition

NOTHING HERE IS A GUESS. No filename, no slice naming convention, no collector
identity string, no regular expression, no execution order, and no sentence
read out of the human report. Every step is a lookup in a structure the
artefact carries.

AND WHERE A LINK IS MISSING IT SAYS SO. A chain that cannot be completed comes
back as an unresolved link naming which one, never as an empty list and never
as a shorter chain that looks complete.
"""

from __future__ import annotations

from typing import Any

#: What a link resolved to, when it did not.
UNATTRIBUTED = "attribution-unavailable"
UNKNOWN_BLOCK = "fact-block-not-in-attribution"


def block_of(path: str) -> str:
    """The fact block a rule's evidence path addresses.

    `permissions.unique_scope_count` is the `unique_scope_count` field of the
    `permissions` block, and the block is what a collector writes and what the
    attribution table is keyed by. A path with no dot addresses a block whole,
    which is how the Conditional Access family used to publish every policy.
    """
    return str(path).split(".", 1)[0]


def chain(result: dict, attribution: dict[str, dict] | None) -> list[dict[str, Any]]:
    """Every acquisition one result depends on, and the paths that reach it.

    A rule reading two facts supplied by two acquisitions comes back with both.
    **No ownership is invented and there is no first-wins**: that would be a
    one-to-one relation the evidence does not have, asserted to make something
    downstream tidy.
    """
    used = result.get("evidence_used") or []
    if not used:
        return []

    reached: dict[str, dict[str, Any]] = {}
    for entry in used:
        path = str((entry or {}).get("path") or "")
        if not path:
            continue
        block = block_of(path)
        # THE IDENTITY IS THE KEY AND THE DESCRIPTION TRAVELS WITH IT. The
        # digest alone was unusable by a surface that opens a run without its
        # documents, and a reader shown `sha256:a891ec...` was being asked to
        # believe it.
        described: dict[str, Any] = {}
        if attribution is None:
            document = UNATTRIBUTED
        else:
            # NOT `entry`. That is the evidence item this loop is reading, and
            # shadowing it made `state` come back from the attribution table --
            # which has none -- so every reading reported an empty state and an
            # `unknown` stopped saying why it was unknown.
            attributed = attribution.get(block)
            if attributed is None:
                document = UNKNOWN_BLOCK
            else:
                document = attributed["document"]
                described = {
                    key: value for key, value in attributed.items() if key != "document"
                }
        found = reached.setdefault(
            document,
            {"document": document, "paths": [], "states": [], **described},
        )
        found["paths"].append(path)
        found["states"].append(str((entry or {}).get("state") or ""))
    return [reached[key] for key in sorted(reached)]


def unresolved(links: list[dict[str, Any]]) -> list[str]:
    """Which links in a chain could not be followed, named.

    An empty chain and a chain that resolves to nothing are different failures
    and are reported as different things. A caller that treated both as "no
    attribution" would report a rule nobody could evaluate exactly as it
    reports a rule whose evidence has no table.
    """
    return sorted(
        {
            link["document"]
            for link in links
            if link["document"] in (UNATTRIBUTED, UNKNOWN_BLOCK)
        }
    )


def decided(result: dict) -> bool:
    """Whether this result is a conclusion rather than a refusal to conclude.

    `unknown` and `invalid_evidence` are outcomes the product is proud of and
    they are not conclusions ABOUT A TENANT. A stage raised on them would be
    claiming that rules decided something when what they decided is that they
    could not.
    """
    return str(result.get("outcome") or "") not in (
        "unknown",
        "invalid_evidence",
        "not_applicable",
    )
