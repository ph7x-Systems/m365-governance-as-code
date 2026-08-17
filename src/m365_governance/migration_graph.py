"""Producing a migration read from Microsoft Graph.

ONE SESSION, ONE TOKEN, EVERY DIMENSION. A `GraphReader` is constructed once by
the caller and spent here. Nothing in this module acquires authentication, and
nothing re-authenticates per dimension: an interactive sign-in per collector is
the single largest measured cost in this product, and repeating that mistake
one level down would make it worse rather than better.

WHAT ONE REQUEST BUYS, AND WHAT COSTS ONE PER ITEM. Listing a folder's children
returns size, authorship and a content hash for every item in the page — three
dimensions for the price of the enumeration. Versions and permissions do not
work that way:

    children listing  →  size · authorship · content        one request per page
    /versions         →  versions                           one request per ITEM
    /permissions      →  permissions · sharing links        one request per ITEM

Graph is explicit that the permissions relationship **cannot be expanded** on a
driveItem or a collection of them. On an estate of a quarter of a million items
that is a quarter of a million requests, so the expensive two are opt-in and a
read that did not ask for them says `out-of-scope` — the operator's decision —
rather than `not-carried`, which would read as a defect.

THE HASH IS PROPRIETARY AND THAT MATTERS. `quickXorHash` is the only hash
guaranteed across OneDrive for work and for home; `sha256Hash` is documented as
unsupported. It compares fine against another Graph read and means nothing
against a SHA-256 of the same bytes, which is why the read records the
algorithm and the comparison refuses to cross the two.

IT NEVER GUESSES WHY SOMETHING IS ABSENT. Every dimension leaves here either
carried, or declared `unsupported` because this surface cannot provide it, or
left out of scope because nobody asked. A downstream that had to infer which
would infer wrong.
"""

from __future__ import annotations

from typing import Any

from .graph import GraphReader, Read

NAME = "graph-migration-read"

#: The hash Graph is documented to provide for both OneDrive flavours. The
#: others are `if available`, and `sha256Hash` is documented as unsupported —
#: reading it would produce a field that is empty on most tenants and present
#: on a few, which is worse than not reading it at all.
DIGEST = "quickXorHash"

#: What the enumeration itself carries, at no extra request.
FROM_LISTING = ("size", "authorship", "content")

#: What costs one request per item, and is therefore opt-in.
PER_ITEM = {"versions": "versions", "permissions": "permissions"}

#: What this surface cannot provide at all. Nothing here is a failure to read;
#: it is the shape of the API, and it will not change by trying again.
NEVER = ()

#: The permissions this read needs, stated the way the other collectors state
#: theirs. Read-only, and the narrower of the two that would work.
PERMISSIONS = ("Files.Read.All", "Sites.Read.All")

#: How deep the walk goes before it stops and says so. A drive has no documented
#: depth limit and Python's recursion does, so without this a deep enough tree
#: ends the collection with a stack trace instead of a coverage gap — which is
#: the difference between a product that reports its limits and one that dies at
#: them.
MAX_DEPTH = 64


class Unreadable(Exception):
    """The estate could not be enumerated, and saying why is the answer."""


def _person(entry: dict[str, Any]) -> str | None:
    """Who Graph says created an item, as one string or nothing.

    `createdBy` may carry a user, an application, or neither. An application is
    recorded rather than dropped: `a migration tool created this` is exactly
    the observation this product exists to surface, and turning it into an
    absence would hide the most common loss there is.
    """
    made_by = entry.get("createdBy") or {}
    for kind in ("user", "application"):
        who = made_by.get(kind) or {}
        name = who.get("displayName") or who.get("email")
        if name:
            return name
    return None


def _item(entry: dict[str, Any]) -> dict[str, Any]:
    """One driveItem, reduced to what a read carries."""
    item: dict[str, Any] = {}
    if isinstance(entry.get("size"), int):
        item["size"] = entry["size"]
    author = _person(entry)
    if author:
        item["author"] = author
    hashes = (entry.get("file") or {}).get("hashes") or {}
    # Present-and-null is a different statement from absent: it says this read
    # looked for a digest and the service had none for this item.
    if "file" in entry:
        item["content_digest"] = hashes.get(DIGEST)
    return item


def _links(permissions: list[dict[str, Any]]) -> list[str]:
    """Sharing links, from the permissions that carry a link facet."""
    found = []
    for permission in permissions:
        link = permission.get("link") or {}
        scope = link.get("scope")
        kind = link.get("type")
        if scope or kind:
            found.append(f"{scope or 'unstated'}:{kind or 'unstated'}")
    return sorted(found)


def _grants(permissions: list[dict[str, Any]]) -> list[list[str]]:
    """Principals and roles, as pairs, sorted so two unchanged reads match."""
    grants = []
    for permission in permissions:
        roles = permission.get("roles") or []
        identity = permission.get("grantedToV2") or permission.get("grantedTo") or {}
        for kind in ("user", "group", "siteGroup", "application"):
            who = identity.get(kind) or {}
            name = who.get("displayName") or who.get("email") or who.get("id")
            if name:
                for role in roles or ["unstated"]:
                    grants.append([name, role])
                break
    return sorted(grants)


def _gap(scope: str, unavailable, what: str) -> dict[str, Any]:
    """One item's failed read, with the one status that means something else.

    A 404 on an AREA means the surface is not served here, and that is what the
    shared vocabulary maps it to. A 404 on an item this walk enumerated seconds
    ago means something different and more ordinary: it was deleted while the
    estate was being read. Estates change under a collector, and calling that
    an unsupported surface would file a normal event as a limitation of the
    method.
    """
    state = unavailable.state
    detail = f"{what}: {unavailable.detail}"
    if state == "not-supported":
        state = "missing"
        detail = (
            f"{what}: this item was listed by the enumeration and was gone "
            "when it was read. Estates change while they are being read"
        )
    return {"scope": scope, "state": state, "detail": detail}


def read(
    reader: GraphReader,
    *,
    drive: str,
    read_id: str,
    taken_at: str,
    estate: str,
    folder: str | None = None,
    with_versions: bool = False,
    with_permissions: bool = False,
) -> dict[str, Any]:
    """A `migration-read` document, from one authenticated session.

    `taken_at` is supplied rather than read from the clock. The moment a read
    was taken decides which side of a move it is, so it belongs to whoever ran
    the collection, not to whichever machine happened to serialise it.
    """
    base = f"drives/{drive}"
    root = f"{base}/items/{folder}" if folder else f"{base}/root"

    items: dict[str, dict[str, Any]] = {}
    coverage: list[dict[str, Any]] = []
    carried_a_digest = False
    #: Folders already entered. A drive can carry a shortcut back to an ancestor,
    #: and a walk without this follows it until the interpreter stops it.
    entered: set[str] = set()

    def walk(path: str, prefix: str, depth: int = 0) -> None:
        nonlocal carried_a_digest
        if depth > MAX_DEPTH:
            coverage.append({
                "scope": prefix or "/",
                "state": "partial",
                "detail": f"the walk stopped at {MAX_DEPTH} levels; anything "
                "below this is not in this read",
            })
            return
        answer: Read = reader.read(f"{path}/children")
        if answer.unavailable is not None:
            coverage.append(
                {
                    "scope": prefix or "/",
                    "state": answer.unavailable.state,
                    "detail": answer.unavailable.detail,
                }
            )
            # What was read before the refusal is kept, and the gap is stated.
            # Discarding a partial read would turn a container we half-saw into
            # a container we claim nothing about.
        for entry in answer.items:
            name = entry.get("name") or entry.get("id") or "<unnamed>"
            identity = f"{prefix}/{name}"
            if "remoteItem" in entry:
                # It lives in another drive. Listing it is honest — it is in
                # this folder — but walking into it would put another estate's
                # items under this estate's identities, and every one of them
                # would then read as present or missing here on the strength of
                # a read that never covered that drive.
                items[identity] = _item(entry)
                coverage.append({
                    "scope": identity,
                    "state": "not-supported",
                    "detail": "this item is shared from another drive; its "
                    "contents are not part of this estate and were not walked",
                })
                continue

            if "folder" in entry:
                if entry["id"] in entered:
                    coverage.append({
                        "scope": identity,
                        "state": "partial",
                        "detail": "this folder was already entered elsewhere in "
                        "the walk, so it was not read twice",
                    })
                    continue
                entered.add(entry["id"])
                walk(f"{base}/items/{entry['id']}", identity, depth + 1)
                continue
            item = _item(entry)
            if "content_digest" in item and item["content_digest"] is not None:
                carried_a_digest = True

            if with_versions:
                versions = reader.read(f"{base}/items/{entry['id']}/versions")
                if versions.unavailable is None:
                    item["versions"] = len(versions.items)
                else:
                    coverage.append(
                        _gap(identity, versions.unavailable, "version history")
                    )

            if with_permissions:
                granted = reader.read(f"{base}/items/{entry['id']}/permissions")
                if granted.unavailable is None:
                    item["permissions"] = _grants(granted.items)
                    item["sharing_links"] = _links(granted.items)
                else:
                    coverage.append(_gap(identity, granted.unavailable, "permissions"))

            items[identity] = item

    walk(root, "")

    if not items and coverage:
        raise Unreadable(
            f"nothing was enumerated under {estate}: {coverage[0]['detail']}"
        )

    document: dict[str, Any] = {
        "$schema": "https://ph7x.com/schemas/m365-governance/migration-read/1.0.0",
        "read_id": read_id,
        "taken_at": taken_at,
        "estate": estate,
        "produced_by": f"{NAME} via {reader.source_api}",
        "coverage": coverage,
        "items": items,
        "read_by": {
            "kind": reader.identity.kind,
            "scopes": list(reader.identity.scopes),
            **({"tenant": reader.identity.observed_tenant_id}
               if reader.identity.observed_tenant_id else {}),
        },
    }

    # What this read cannot provide, as opposed to what it did not fetch. Only
    # the first belongs in `unsupported`; the second is the operator's choice
    # and reaches the comparison as `out-of-scope` because the dimension is
    # simply not carried and the record says who decided.
    unsupported = list(NEVER)
    if unsupported:
        document["unsupported"] = unsupported
    if carried_a_digest:
        document["content_digest_algorithm"] = DIGEST

    return document
