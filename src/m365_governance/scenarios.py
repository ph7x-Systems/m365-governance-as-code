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
from datetime import UTC, datetime, timedelta
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


def _sources(used: list[dict]) -> dict:
    """What an inspection was made from: how many documents, and which."""
    stamps = sorted(
        stamp
        for stamp in ((d.get("provenance") or {}).get("collected_at") for d in used)
        if stamp
    )
    return {
        "documents": len(used),
        "digest": _digest(used),
        "collected_from": stamps[0] if stamps else None,
        "collected_to": stamps[-1] if stamps else None,
        "identity_kinds": sorted(
            {str((d.get("provenance") or {}).get("identity_kind") or "") for d in used}
            - {""}
        ),
    }


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
        "sources": _sources(used),
    }


def ownership(documents: list[dict], minimum_owners: int = 2) -> dict:
    """Which SharePoint sites name enough administrators, and which cannot say.

    Reads who administers each site (`owners`, read site by site) and compares
    the number of administrators that can be counted with a number the
    operator chose. The threshold is the operator's and is recorded in the
    inspection; this engine holds no view on what it should be.

    A GROUP IS NOT A NUMBER OF PEOPLE. An administrator that is a group was
    not expanded, so a site with one named person and one group has at least
    two administrators and possibly many: it is reported as `at-least` when
    the named ones already reach the threshold and as `not-established` when
    they do not, never as too few.
    """
    sites = [
        d
        for d in documents
        if (d.get("resource") or {}).get("workload") == "sharepoint"
        and (d.get("resource") or {}).get("type") == "site"
    ]
    with_read = [
        d for d in sites if isinstance((d.get("facts") or {}).get("owners"), dict)
    ]
    chosen, duplicated = _latest(with_read)
    for document in sites:
        key = str((document.get("resource") or {}).get("native_id") or "")
        if key and key not in chosen:
            chosen[key] = document

    rows = []
    for key in sorted(chosen):
        document = chosen[key]
        resource = document.get("resource") or {}
        owners = (document.get("facts") or {}).get("owners")
        row: dict[str, Any] = {
            "native_id": key,
            "name": resource.get("display_name") or "",
            "url": resource.get("url") or "",
            "named_administrators": "",
            "group_administrators": "",
            "collected_at": (document.get("provenance") or {}).get("collected_at"),
        }
        if not isinstance(owners, dict):
            row["owners_read"] = "[not-collected]"
            row["standing"] = NOT_ESTABLISHED
            row["because"] = "who administers this site was not read"
        elif owners.get("state") != "observed":
            row["owners_read"] = f"[{owners.get('state') or NOT_ESTABLISHED}]"
            row["standing"] = NOT_ESTABLISHED
            row["because"] = (
                "the site did not say who administers it; that is not a site "
                "with no administrators"
            )
        else:
            named = _observed(owners.get("direct_count"))
            groups = _observed(owners.get("group_count"))
            if named is None:
                named = len(owners.get("direct") or [])
            if groups is None:
                groups = len(owners.get("groups") or [])
            row["owners_read"] = "observed"
            row["named_administrators"] = named
            row["group_administrators"] = groups
            if named >= minimum_owners:
                row["standing"] = "at-least" if groups else "meets"
                row["because"] = f"{named} named administrators" + (
                    ", and groups that were not expanded" if groups else ""
                )
            elif groups:
                row["standing"] = NOT_ESTABLISHED
                row["because"] = (
                    f"{named} named administrators and {groups} groups whose "
                    "members were not read, so the number of people cannot be "
                    "compared with the threshold"
                )
            else:
                row["standing"] = "fewer"
                row["because"] = f"{named} named administrators and no group"
        rows.append(row)

    by_standing: dict[str, int] = {}
    for row in rows:
        by_standing[row["standing"]] = by_standing.get(row["standing"], 0) + 1

    return {
        "$schema": SCHEMA,
        "scenario": "ownership",
        "scope": "spo",
        "question": (
            f"Which SharePoint sites name at least {minimum_owners} "
            "administrators, and which cannot say?"
        ),
        "parameters": {"minimum_owners": minimum_owners},
        "columns": [
            "name",
            "url",
            "owners_read",
            "named_administrators",
            "group_administrators",
            "standing",
            "because",
        ],
        "relations": [
            "site -> its site collection administrators, read from the site itself",
            "group administrator -> its members: NOT JOINED. A group was not "
            "expanded into people",
        ],
        "rows": rows,
        "sites": {
            "in_the_evidence": len(rows),
            "by_standing": dict(sorted(by_standing.items())),
        },
        "duplicates": duplicated,
        "not_established": [
            "the people behind an administrator that is a group: no group was "
            "expanded, so a site administered by a group has an unknown number "
            "of administrators",
            "the owners of the Microsoft 365 group or the team connected to a "
            "site: a site collection administrator, a group owner and a team "
            "owner are three different things and only the first was read",
            "whether an administrator is active, reachable or still employed: "
            "an account being named is not a person being responsible",
            "sites the collecting identity could not enumerate or open: the "
            "first are absent from the evidence, the second are rows that say so",
        ],
        "sources": _sources([chosen[key] for key in sorted(chosen)]),
    }


def _moment(text: Any) -> datetime | None:
    """A timestamp as the service or a collector wrote it, or nothing."""
    if not isinstance(text, str) or not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def app_exposure(documents: list[dict], expires_within_days: int = 30) -> dict:
    """Which applications hold a credential that has ended or is about to.

    MEASURED FROM WHEN THE EVIDENCE WAS COLLECTED, NEVER FROM NOW. An
    inspection run a month later over the same evidence gives the same rows:
    `ending` means within the window after the collection, and the collection
    time is on every row. Somebody reading old evidence is told how old.

    The window is the operator's and is recorded. An application whose
    credentials were not returned is `not-established`, never `no-credentials`:
    only an observed empty list is an application with nothing to expire.
    """
    window = timedelta(days=expires_within_days)
    applications, duplicated = _latest(
        [
            d
            for d in documents
            if (d.get("resource") or {}).get("type") == "application"
            and isinstance((d.get("facts") or {}).get("application"), dict)
        ]
    )
    rows = []
    for key in sorted(applications):
        document = applications[key]
        resource = document.get("resource") or {}
        collected = (document.get("provenance") or {}).get("collected_at")
        at = _moment(collected)
        credentials = _observed(_fact(document, "application", "credentials"))
        row: dict[str, Any] = {
            "native_id": key,
            "name": resource.get("display_name") or "",
            "app_id": _observed(_fact(document, "application", "app_id")) or "",
            "collected_at": collected,
            "ended": "",
            "ending": "",
            "later": "",
            "earliest_end": "",
            "requested_application_permissions": _observed(
                _fact(document, "application", "requested_application_permissions")
            ),
            "requested_delegated_permissions": _observed(
                _fact(document, "application", "requested_delegated_permissions")
            ),
        }
        for name in (
            "requested_application_permissions",
            "requested_delegated_permissions",
        ):
            if row[name] is None:
                row[name] = f"[{NOT_ESTABLISHED}]"
        if not isinstance(credentials, list) or at is None:
            row["standing"] = NOT_ESTABLISHED
            row["because"] = (
                "the credentials of this application were not returned"
                if at is not None
                else "the evidence does not say when it was collected"
            )
        else:
            ends = [_moment(c.get("ends_at")) for c in credentials]
            undated = sum(1 for end in ends if end is None)
            dated = sorted(end for end in ends if end is not None)
            ended = [end for end in dated if end <= at]
            ending = [end for end in dated if at < end <= at + window]
            row["ended"] = len(ended)
            row["ending"] = len(ending)
            row["later"] = len(dated) - len(ended) - len(ending)
            if dated:
                row["earliest_end"] = dated[0].strftime("%Y-%m-%dT%H:%M:%SZ")
            if not credentials:
                row["standing"] = "no-credentials"
                row["because"] = "the application holds no secret and no certificate"
            elif ended:
                row["standing"] = "ended"
                row["because"] = f"{len(ended)} credentials had ended at collection"
            elif ending:
                row["standing"] = "ending"
                row["because"] = (
                    f"{len(ending)} credentials end within "
                    f"{expires_within_days} days of the collection"
                )
            elif undated:
                row["standing"] = NOT_ESTABLISHED
                row["because"] = f"{undated} credentials carry no end date"
            else:
                row["standing"] = "later"
                row["because"] = "every credential ends after the window"
        rows.append(row)

    by_standing: dict[str, int] = {}
    for row in rows:
        by_standing[row["standing"]] = by_standing.get(row["standing"], 0) + 1

    return {
        "$schema": SCHEMA,
        "scenario": "app-exposure",
        "scope": "entra",
        "question": (
            "Which application registrations hold a credential that had ended, "
            f"or ends within {expires_within_days} days, when the evidence was "
            "collected?"
        ),
        "parameters": {"expires_within_days": expires_within_days},
        "columns": [
            "name",
            "app_id",
            "standing",
            "ended",
            "ending",
            "later",
            "earliest_end",
            "requested_application_permissions",
            "requested_delegated_permissions",
            "collected_at",
            "because",
        ],
        "relations": [
            "application -> its own credentials, carried on the registration",
            "application -> what was consented to: NOT JOINED. The permissions "
            "shown are what the registration asks for",
        ],
        "rows": rows,
        "applications": {
            "in_the_evidence": len(rows),
            "by_standing": dict(sorted(by_standing.items())),
        },
        "duplicates": duplicated,
        "not_established": [
            "what any application was in fact granted: consent lives on the "
            "service principal and in the grants, which were not read",
            "whether a credential is in use: one that ended may belong to an "
            "application nobody runs, and one that ends later may be the only "
            "thing keeping a service alive",
            "who is responsible for an application: owners were not read",
            "credentials held by service principals rather than by the "
            "registration: a different object, not read",
        ],
        "sources": _sources([applications[key] for key in sorted(applications)]),
    }


#: Scenario name -> (what it answers, the function, the collections it reads).
SCENARIOS: dict[str, tuple[str, Callable[[list[dict]], dict], tuple[str, ...]]] = {
    "external-access": (
        "which SharePoint sites permit sharing outside the organisation",
        external_access,
        ("sites-sharing", "tenant-sharing", "guests"),
    ),
    "app-exposure": (
        "which applications hold a credential that has ended or is about to",
        app_exposure,
        ("applications",),
    ),
    "ownership": (
        "which SharePoint sites name enough administrators, and which cannot say",
        ownership,
        ("sites-owners",),
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
    columns = list(inspection.get("columns") or COLUMNS)
    rows = [
        [str(row.get(column, "")) for column in columns] for row in inspection["rows"]
    ]
    return columns, rows


def _row_lines(inspection: dict, row: dict) -> list[str]:
    if inspection["scenario"] == "app-exposure":
        return [
            f"  standing         {row['standing']}  ({row['because']})",
            f"  credentials      ended {row['ended'] if row['ended'] != '' else '-'}"
            f" · ending {row['ending'] if row['ending'] != '' else '-'}"
            f" · later {row['later'] if row['later'] != '' else '-'}"
            f" · earliest end {row['earliest_end'] or '-'}",
            f"  asks for         application "
            f"{row['requested_application_permissions']} · delegated "
            f"{row['requested_delegated_permissions']}  (asked, not granted)",
        ]
    if inspection["scenario"] == "ownership":
        named = row["named_administrators"]
        groups = row["group_administrators"]
        return [
            f"  standing         {row['standing']}  ({row['because']})",
            f"  administrators   read: {row['owners_read']} · named "
            f"{'-' if named == '' else named} · groups "
            f"{'-' if groups == '' else groups}",
        ]
    return [
        f"  in force         {row['in_force']}  ({row['because']})",
        f"  site / org       {row['site_capability']} / "
        f"{row['organisation_capability']}",
        f"  external sharing {row['external_sharing']} · new guests "
        f"{row['new_guests']} · anonymous links {row['anonymous_links']}",
    ]


def as_text(inspection: dict) -> str:
    lines = [inspection["question"], ""]
    counted = inspection.get("sites") or inspection.get("applications") or {}
    noun = "application" if "applications" in inspection else "SharePoint site"
    if not inspection["rows"]:
        lines += [f"No {noun} is in this evidence.", ""]
    for row in inspection["rows"]:
        title = row["name"] or row["native_id"]
        lines.append(f"{title}  {row.get('url') or row.get('app_id') or ''}".rstrip())
        lines += _row_lines(inspection, row)
        lines.append("")
    lines.append(f"{counted.get('in_the_evidence', 0)} {noun}s in the evidence:")
    for state, number in (counted.get("by_external_sharing") or {}).items():
        lines.append(f"  external sharing {state}: {number}")
    for state, number in (counted.get("by_standing") or {}).items():
        lines.append(f"  {state}: {number}")
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
    made_from = f"From {sources['documents']} evidence documents"
    if sources["documents"]:
        made_from += (
            f", {sources['digest'][:19]}…, collected "
            f"{sources['collected_from']} to {sources['collected_to']}"
        )
    lines += ["", made_from + ".", ""]
    return "\n".join(lines)
