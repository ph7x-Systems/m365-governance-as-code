"""Which thing a resource is, in one place.

WHY NOT `<service>:<type>:<native-id>`. The audit proposed a parsed string and
it does not survive real identifiers. A SharePoint site's native id IS its URL,
so splitting on a colon yields `https` as the first field. Escaping would be a
grammar nobody validates, and every consumer would re-implement the parser —
the second authority this contract exists to remove. The two leading fields
also duplicate `type`, which the resource already carries.

SO IDENTITY IS STRUCTURED AND THE NATIVE ID IS A VALUE. Three fields, compared
structurally, and nothing anywhere reads inside the third. A URL, a GUID, a
path, something full of colons: all lossless, because nothing parses it.

WORKLOAD IS NOT DECORATION. Without it two workloads can name the same string
and mean different things — a Team and a site can share a URL, an Exchange
mailbox and a OneDrive can share an address — and a comparison would pair two
resources that are not the same resource.

DISPLAY IS NOT IDENTITY. `display_name` and `url` are what a product's
navigation happens to call something today. A name is how a classifier starts
lying, and an identity that moved when somebody renamed a site would make an
archive unreadable against the next one.
"""

from __future__ import annotations

#: The fields that identify a resource, in the order they are written.
FIELDS = ("workload", "type", "native_id")


def ref(resource: dict) -> dict:
    """The reference form of one resource: what a parent or a result carries."""
    return {field: resource[field] for field in FIELDS}


def key(resource: dict | None) -> tuple:
    """A comparable key. Structural equality, never a formatted string.

    Returned as a tuple so it can index a dictionary and sort deterministically
    without anyone inventing a separator — a separator is a grammar, and a
    grammar is something to parse.
    """
    if resource is None:
        return ()
    return tuple(resource.get(field, "") for field in FIELDS)


def same(left: dict | None, right: dict | None) -> bool:
    return key(left) == key(right)


def label(resource: dict) -> str:
    """What to print. Display only, and never used to decide anything."""
    return resource.get("display_name") or resource.get("native_id", "<unknown>")


def readable(resource: dict | None) -> str:
    """An identity a person can read in one line, for a message or a heading.

    Assembled for a human at the moment of printing, and never stored, parsed
    or compared. That is the difference between this and the string grammar
    that was rejected: nothing reads it back.
    """
    if not resource:
        return "<unknown>"
    return (
        f"{resource.get('workload', '?')} {resource.get('type', '?')} "
        f"{resource.get('native_id', '?')}"
    )
