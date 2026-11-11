"""Composed scenarios: one question answered from several collections.

    collector -> dataset -> join -> inspection

A scenario reads evidence that was already collected and relates it. It makes
no call to a tenant, so the same evidence always gives the same inspection,
and it brings no reading of a Microsoft surface of its own: every value it
shows is a fact some collector published, with that collector's state.

NOTHING IS LOST AND NOTHING IS FILLED IN. A resource that appears in the
evidence appears in the inspection. When the fact a scenario needs was not
read for it, the row says `not-established` and why; it is never dropped and
never given the value its neighbours have. Two documents for one resource are
reported as a duplicate, with the later one used.

AN INSPECTION IS NOT AN ASSESSMENT. It relates what was observed and names
what it could not establish. It reaches no outcome, counts nothing as good or
bad, and publishes no total over unlike things: rules do the first, and the
programme's charter forbids the last.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import collecting

SCHEMA = "https://ph7x.com/schemas/m365-governance/inspection/1.0.0"

NOT_ESTABLISHED = "not-established"

#: SharePoint's own names for what a site or an organisation permits, from the
#: most restrictive to the least. The order is Microsoft's: each value permits
#: what the one before it permits, and one thing more. Source: the
#: `SharingCapability` parameter of Set-SPOSite and Set-SPOTenant.
SHARING_ORDER = (
    "Disabled",
    "ExistingExternalUserSharingOnly",
    "ExternalUserSharingOnly",
    "ExternalUserAndGuestSharing",
)

#: What each value permits, in the reference's words. A value this table does
#: not hold is reported as `not-established` rather than guessed at.
SHARING_MEANS = {
    "Disabled": {
        "external_sharing": "not-permitted",
        "new_guests": "not-permitted",
        "anonymous_links": "not-permitted",
    },
    "ExistingExternalUserSharingOnly": {
        "external_sharing": "permitted",
        "new_guests": "not-permitted",
        "anonymous_links": "not-permitted",
    },
    "ExternalUserSharingOnly": {
        "external_sharing": "permitted",
        "new_guests": "permitted",
        "anonymous_links": "not-permitted",
    },
    "ExternalUserAndGuestSharing": {
        "external_sharing": "permitted",
        "new_guests": "permitted",
        "anonymous_links": "permitted",
    },
}


def load(directory: Path) -> list[dict]:
    """Every evidence document under a directory, and nothing that is not one."""
    documents = []
    for path in sorted(Path(directory).rglob("*.json")):
        if path.name.startswith(collecting.NOT_EVIDENCE):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "resource" in data and "facts" in data:
            documents.append(data)
    return documents


def _digest(documents: list[dict]) -> str:
    canonical = json.dumps(documents, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fact(document: dict, family: str, name: str) -> dict | None:
    found = (document.get("facts") or {}).get(family)
    if not isinstance(found, dict):
        return None
    fact = found.get(name)
    return fact if isinstance(fact, dict) else None


def _observed(fact: dict | None) -> Any:
    if fact is not None and fact.get("state") == "observed":
        return fact.get("value")
    return None


def _why(fact: dict | None, absent: str) -> str:
    if fact is None:
        return absent
    return str(fact.get("state") or NOT_ESTABLISHED)


def _latest(documents: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """One document per resource: the latest read. And which were duplicated."""
    chosen: dict[str, dict] = {}
    duplicated: list[str] = []
    for document in documents:
        key = str((document.get("resource") or {}).get("native_id") or "")
        if not key:
            continue
        if key in chosen:
            if key not in duplicated:
                duplicated.append(key)
            held = (chosen[key].get("provenance") or {}).get("collected_at") or ""
            this = (document.get("provenance") or {}).get("collected_at") or ""
            if this < held:
                continue
        chosen[key] = document
    return chosen, sorted(duplicated)


def _guests(documents: list[dict]) -> dict:
    """What a guest collection in the evidence says, as counts of accounts.

    Each number counts guest accounts in one stated condition. They are not
    added to anything and nothing is concluded from them: an enabled guest
    whose invitation was accepted is an account that can sign in, and where it
    can go was not read.
    """
    tenants = [
        d
        for d in documents
        if (d.get("resource") or {}).get("type") == "tenant"
        and isinstance((d.get("facts") or {}).get("guests"), dict)
    ]
    accounts, _ = _latest(
        [
            d
            for d in documents
            if (d.get("resource") or {}).get("type") == "user"
            and isinstance((d.get("facts") or {}).get("guest"), dict)
        ]
    )
    if not tenants and not accounts:
        return {"state": "not-collected", "_documents": []}
    newest = max(
        tenants,
        key=lambda d: (d.get("provenance") or {}).get("collected_at") or "",
        default={},
    )
    count = _fact(newest, "guests", "count")
    state = "observed" if _observed(count) is not None else _why(count, "missing")

    def holding(name: str, value: Any) -> int:
        return sum(
            1 for d in accounts.values() if _observed(_fact(d, "guest", name)) == value
        )

    return {
        "state": state,
        "accounts_read": len(accounts),
        "accounts_enabled": holding("account_enabled", True),
        "accounts_disabled": holding("account_enabled", False),
        "invitations_accepted": holding("invitation_state", "Accepted"),
        "invitations_pending": holding("invitation_state", "PendingAcceptance"),
        "_documents": [accounts[key] for key in sorted(accounts)]
        + ([newest] if newest else []),
    }


def external_access(documents: list[dict]) -> dict:
    """Which SharePoint sites permit sharing outside the organisation.

    Joins what each site permits (`sharing.capability`, read site by site) to
    what the organisation permits (`tenant_sharing.capability`), on the tenant
    host both documents carry. SharePoint does not let a site permit more than
    its organisation, so the less permissive of the two is what is in force;
    when the organisation's value was not read, the row carries the site's own
    value and says the bound was not established.
    """
    tenants: dict[str, dict] = {}
    sites: list[dict] = []
    for document in documents:
        resource = document.get("resource") or {}
        if resource.get("workload") != "sharepoint":
            continue
        if resource.get("type") == "tenant":
            if _fact(document, "tenant_sharing", "capability") is not None:
                tenants[str(resource.get("native_id") or "")] = document
        elif resource.get("type") == "site":
            sites.append(document)

    # A SITE WITH A SHARING READ WINS OVER THE SAME SITE WITHOUT ONE, so an
    # enumeration document cannot hide the read that answered the question.
    with_read = [d for d in sites if _fact(d, "sharing", "capability") is not None]
    chosen, duplicated = _latest(with_read)
    for document in sites:
        key = str((document.get("resource") or {}).get("native_id") or "")
        if key and key not in chosen:
            chosen[key] = document

    rows = []
    for key in sorted(chosen):
        document = chosen[key]
        resource = document.get("resource") or {}
        host = str((resource.get("tenant") or {}).get("host") or "")
        own_fact = _fact(document, "sharing", "capability")
        own = _observed(own_fact)
        bound_fact = _fact(tenants.get(host, {}), "tenant_sharing", "capability")
        bound = _observed(bound_fact)

        row: dict[str, Any] = {
            "native_id": key,
            "name": resource.get("display_name") or "",
            "url": resource.get("url") or "",
            "tenant": host,
            "site_capability": own
            if own is not None
            else f"[{_why(own_fact, 'not-collected')}]",
            "organisation_capability": bound
            if bound is not None
            else f"[{_why(bound_fact, 'not-collected')}]",
            "collected_at": (document.get("provenance") or {}).get("collected_at"),
        }

        if own not in SHARING_MEANS:
            in_force = None
            row["because"] = (
                "this site's sharing setting was not read"
                if own is None
                else f"{own} is not a value this engine has a documented meaning for"
            )
        elif bound in SHARING_MEANS:
            in_force = min(own, bound, key=SHARING_ORDER.index)
            row["because"] = (
                "the site's own setting"
                if in_force == own
                else "bounded by what the organisation permits"
            )
        else:
            in_force = own
            row["because"] = (
                "the site's own setting; what the organisation permits was not "
                "read, so the bound it places on this site is not established"
            )

        row["in_force"] = in_force or NOT_ESTABLISHED
        means = SHARING_MEANS.get(in_force or "", {})
        for name in ("external_sharing", "new_guests", "anonymous_links"):
            row[name] = means.get(name, NOT_ESTABLISHED)
        rows.append(row)

    directory = _guests(documents)

    by_state: dict[str, int] = {}
    for row in rows:
        by_state[row["external_sharing"]] = by_state.get(row["external_sharing"], 0) + 1

    used = (
        [chosen[key] for key in sorted(chosen)]
        + [tenants[key] for key in sorted(tenants)]
        + directory.pop("_documents")
    )
    not_established = [
        "whether anything on a site is in fact shared: a setting says what "
        "is permitted, and neither sharing links nor site membership were "
        "read",
        "which person outside the organisation can reach which site: that "
        "needs site membership or sharing links joined to a guest's object "
        "id, and neither was read",
        "sites the collecting identity could not enumerate: they are absent "
        "from the evidence and their number is not knowable from it",
    ]
    if directory["state"] != "observed":
        not_established.insert(
            0,
            "which guests exist in the directory: "
            + (
                "no guest collection is in this evidence"
                if directory["state"] == "not-collected"
                else f"the guest read ended as {directory['state']}, so what "
                "was read is a lower bound"
            ),
        )
    return {
        "$schema": SCHEMA,
        "scenario": "external-access",
        "scope": "spo",
        "question": (
            "Which SharePoint sites permit sharing outside the organisation, "
            "and how far?"
        ),
        "relations": [
            "site -> organisation, on the tenant host both documents carry",
            "guest -> site: NOT JOINED. A guest account existing and a site "
            "permitting guests are two facts side by side; nothing read here "
            "connects one to the other",
        ],
        "guests": directory,
        "rows": rows,
        "sites": {
            "in_the_evidence": len(rows),
            "by_external_sharing": dict(sorted(by_state.items())),
        },
        "duplicates": duplicated,
        "not_established": not_established,
        "sources": {
            "documents": len(used),
            "digest": _digest(used),
            "collected_from": min(
                ((d.get("provenance") or {}).get("collected_at") or "" for d in used),
                default="",
            ),
            "collected_to": max(
                ((d.get("provenance") or {}).get("collected_at") or "" for d in used),
                default="",
            ),
            "identity_kinds": sorted(
                {
                    str((d.get("provenance") or {}).get("identity_kind") or "")
                    for d in used
                }
                - {""}
            ),
        },
    }


#: Scenario name -> (what it answers, the function, the collections it reads).
SCENARIOS: dict[str, tuple[str, Callable[[list[dict]], dict], tuple[str, ...]]] = {
    "external-access": (
        "which SharePoint sites permit sharing outside the organisation",
        external_access,
        ("sites-sharing", "tenant-sharing", "guests"),
    ),
}

COLUMNS = (
    "name",
    "url",
    "site_capability",
    "organisation_capability",
    "in_force",
    "external_sharing",
    "new_guests",
    "anonymous_links",
    "because",
)


def as_table(inspection: dict) -> tuple[list[str], list[list[str]]]:
    rows = [
        [str(row.get(column, "")) for column in COLUMNS] for row in inspection["rows"]
    ]
    return list(COLUMNS), rows


def as_text(inspection: dict) -> str:
    lines = [inspection["question"], ""]
    if not inspection["rows"]:
        lines += ["No SharePoint site is in this evidence.", ""]
    for row in inspection["rows"]:
        title = row["name"] or row["native_id"]
        lines.append(f"{title}  {row['url']}".rstrip())
        lines.append(f"  in force         {row['in_force']}  ({row['because']})")
        lines.append(
            f"  site / org       {row['site_capability']} / "
            f"{row['organisation_capability']}"
        )
        lines.append(
            f"  external sharing {row['external_sharing']} · new guests "
            f"{row['new_guests']} · anonymous links {row['anonymous_links']}"
        )
        lines.append("")
    counted = inspection["sites"]
    lines.append(f"{counted['in_the_evidence']} sites in the evidence:")
    for state, number in counted["by_external_sharing"].items():
        lines.append(f"  external sharing {state}: {number}")
    if inspection["duplicates"]:
        lines.append(
            f"  {len(inspection['duplicates'])} sites were in the evidence more "
            "than once; the latest read of each was used"
        )
    directory = inspection.get("guests") or {}
    if directory.get("state", "not-collected") != "not-collected":
        lines += [
            "",
            f"Guest accounts in the directory (read: {directory['state']}):",
            f"  accounts read {directory['accounts_read']} · enabled "
            f"{directory['accounts_enabled']} · disabled "
            f"{directory['accounts_disabled']}",
            f"  invitations accepted {directory['invitations_accepted']} · "
            f"pending {directory['invitations_pending']}",
            "  These accounts exist. Which sites any of them can reach was not read.",
        ]
    lines += ["", "Not established by this inspection:"]
    lines += [f"  - {item}" for item in inspection["not_established"]]
    sources = inspection["sources"]
    lines += [
        "",
        f"From {sources['documents']} evidence documents, {sources['digest'][:19]}…, "
        f"collected {sources['collected_from']} to {sources['collected_to']}.",
        "",
    ]
    return "\n".join(lines)
