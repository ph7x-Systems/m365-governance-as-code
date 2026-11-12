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
import re
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

    # WHICH GUESTS EACH SITE HAS MET, by the directory's own identifier. A
    # site's list of users is joined to the directory's guests on the object
    # id both carry. Being in the list is not having access, and the join
    # says which side of it each identifier was found on and nothing more.
    met_reads, _ = _latest(
        [
            d
            for d in sites
            if isinstance((d.get("facts") or {}).get("site_guests"), dict)
        ]
    )
    listed = {
        str((d.get("resource") or {}).get("native_id") or "").lower()
        for d in directory["_documents"]
        if (d.get("resource") or {}).get("type") == "user"
    }
    met_by: dict[str, int] = {}
    for row in rows:
        read = met_reads.get(row["native_id"])
        count = _fact(read or {}, "site_guests", "guests")
        ids = _observed(_fact(read or {}, "site_guests", "guest_object_ids"))
        if read is None:
            row["guests_met"] = "[not-collected]"
        elif _observed(count) is None:
            row["guests_met"] = f"[{_why(count, 'missing')}]"
        else:
            row["guests_met"] = _observed(count)
            for identifier in ids if isinstance(ids, list) else []:
                key = str(identifier).lower()
                met_by[key] = met_by.get(key, 0) + 1
    if met_reads:
        directory["met_by_sites"] = {
            "distinct_guest_accounts": len(met_by),
            "also_listed_as_guests": (
                len(set(met_by) & listed) if directory["state"] == "observed" else None
            ),
            "not_listed_as_guests": (
                len(set(met_by) - listed) if directory["state"] == "observed" else None
            ),
            "listed_and_met_by_no_site": (
                len(listed - set(met_by)) if directory["state"] == "observed" else None
            ),
        }

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
    if met_reads:
        not_established[1] = (
            "which person outside the organisation can open which site today: "
            "a site's list of users says the site has met an account, an "
            "entry stays after a permission is removed, and a guest reached "
            "through a group may have access with no entry of their own"
        )
        not_established.insert(
            2,
            "what an account is that a site has met and the directory does not "
            "list as a guest: it may have been removed from the directory, or "
            "be an external account whose type is not Guest. Neither was read",
        )
        used += [met_reads[key] for key in sorted(met_reads)]
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
            (
                "guest -> site, on the directory object id a site's list of "
                "users and the directory both carry: the site HAS MET the "
                "account, which is not the account having access"
                if met_reads
                else "guest -> site: NOT JOINED. A guest account existing and "
                "a site permitting guests are two facts side by side; nothing "
                "read here connects one to the other"
            ),
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

    # THE GROUP A SITE IS CONNECTED TO, by the identifier the site enumeration
    # publishes, and the group's own document by the same identifier. An empty
    # identifier is SharePoint's way of saying the site has no group.
    nothing = "00000000-0000-0000-0000-000000000000"
    connected: dict[str, str] = {}
    for document in sites:
        identifier = _observed(_fact(document, "site", "group_id"))
        if isinstance(identifier, str) and identifier and identifier != nothing:
            key = str((document.get("resource") or {}).get("native_id") or "")
            connected[key] = identifier.lower()
    found, _ = _latest(
        [
            d
            for d in documents
            if (d.get("resource") or {}).get("type") == "group"
            and isinstance((d.get("facts") or {}).get("group"), dict)
        ]
    )
    by_group = {key.lower(): value for key, value in found.items()}
    enumerated = {
        str((d.get("resource") or {}).get("native_id") or "")
        for d in sites
        if _fact(d, "site", "group_id") is not None
    }
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
        # THE CONNECTED GROUP'S OWNERS, BESIDE THE SITE'S ADMINISTRATORS.
        group_owners = None
        if key not in enumerated:
            row["connected_group"] = "[not-collected]"
            row["group_user_owners"] = ""
        elif key not in connected:
            row["connected_group"] = "none"
            row["group_user_owners"] = ""
        elif connected[key] not in by_group:
            row["connected_group"] = "connected"
            row["group_user_owners"] = "[not-collected]"
        else:
            owners_fact = _fact(by_group[connected[key]], "group", "user_owners")
            group_owners = _observed(owners_fact)
            row["connected_group"] = "connected"
            row["group_user_owners"] = (
                group_owners
                if group_owners is not None
                else f"[{_why(owners_fact, 'missing')}]"
            )

        # ONE GROUP CAN BE EXPANDED, AND ONLY ONE. When every group among the
        # site's administrators is the owners claim of the group the site is
        # connected to -- the same identifier, read from two surfaces -- the
        # people behind it are that group's owners, and they were counted. A
        # named administrator may also be one of those owners and no identity
        # was kept to tell, so the result is a range and never a sum: at least
        # the larger of the two, at most both together.
        row["administrators_at_least"] = ""
        row["administrators_at_most"] = ""
        if (
            isinstance(owners, dict)
            and owners.get("state") == "observed"
            and isinstance(group_owners, int)
            and row["group_administrators"]
            and _only_the_owners_of(owners.get("groups") or [], connected[key])
        ):
            named = row["named_administrators"]
            low, high = max(named, group_owners), named + group_owners
            row["administrators_at_least"], row["administrators_at_most"] = low, high
            if low >= minimum_owners:
                row["standing"] = "meets" if low == high else "at-least"
                row["because"] = (
                    f"{named} named administrators and the {group_owners} user "
                    "owners of its Microsoft 365 group, which is the group "
                    "that administers it"
                )
            elif high < minimum_owners:
                row["standing"] = "fewer"
                row["because"] = (
                    f"{named} named administrators and the {group_owners} user "
                    "owners of its Microsoft 365 group: at most "
                    f"{high} people"
                )
            else:
                row["standing"] = NOT_ESTABLISHED
                row["because"] = (
                    f"between {low} and {high} people: {named} named and "
                    f"{group_owners} group owners, and whether they are the "
                    "same people was not read"
                )
        rows.append(row)

    by_standing: dict[str, int] = {}
    for row in rows:
        by_standing[row["standing"]] = by_standing.get(row["standing"], 0) + 1
    joined = [by_group[g] for g in sorted(set(connected.values())) if g in by_group]

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
            "administrators_at_least",
            "administrators_at_most",
            "connected_group",
            "group_user_owners",
            "because",
        ],
        "relations": [
            "site -> its site collection administrators, read from the site itself",
            "site -> its Microsoft 365 group, on the group identifier the site "
            "enumeration publishes",
            "site administrator that is a group -> that group's owners, only "
            "when the administrator is the owners claim of the connected "
            "group, by the same identifier; the people are then counted as a "
            "range, because nothing read says whether a named administrator "
            "is also an owner",
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
            (
                "the owners of the Microsoft 365 group connected to a site are "
                "shown beside it where they were read, and are not its "
                "administrators: a site collection administrator, a group "
                "owner and a team owner are three different things"
                if joined
                else "the owners of the Microsoft 365 group or the team "
                "connected to a site: a site collection administrator, a "
                "group owner and a team owner are three different things and "
                "only the first was read"
            ),
            "whether an administrator is active, reachable or still employed: "
            "an account being named is not a person being responsible",
            "sites the collecting identity could not enumerate or open: the "
            "first are absent from the evidence, the second are rows that say so",
        ],
        "sources": _sources([chosen[key] for key in sorted(chosen)] + joined),
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
    # THE REGISTRATION AND ITS SERVICE PRINCIPAL, on the application
    # identifier both carry. A registration with no service principal cannot
    # sign in to this directory; one whose service principal is disabled
    # cannot either. Neither is concluded when no service principal
    # collection is in the evidence.
    principals, _ = _latest(
        [
            d
            for d in documents
            if (d.get("resource") or {}).get("type") == "service-principal"
            and isinstance((d.get("facts") or {}).get("service_principal"), dict)
        ]
    )
    by_app: dict[str, dict] = {}
    for principal in principals.values():
        app_id = _observed(_fact(principal, "service_principal", "app_id"))
        if isinstance(app_id, str) and app_id:
            by_app[app_id.lower()] = principal
    registered = set()

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
        app_id = str(row["app_id"]).lower()
        registered.add(app_id)
        if not principals:
            row["can_sign_in_here"] = "[not-collected]"
        elif app_id not in by_app:
            row["can_sign_in_here"] = "no: no service principal in this directory"
        else:
            enabled_fact = _fact(by_app[app_id], "service_principal", "account_enabled")
            enabled = _observed(enabled_fact)
            row["can_sign_in_here"] = (
                f"[{_why(enabled_fact, 'missing')}]"
                if enabled is None
                else "yes"
                if enabled
                else "no: its service principal is disabled"
            )
        rows.append(row)

    by_standing: dict[str, int] = {}
    for row in rows:
        by_standing[row["standing"]] = by_standing.get(row["standing"], 0) + 1

    # SERVICE PRINCIPALS WITH NO REGISTRATION HERE: applications that belong
    # to somebody else, or to Microsoft. Counted by what the service says
    # about whose they are, and never listed as a finding: most of a
    # directory's service principals are Microsoft's own.
    elsewhere = {
        "of_this_directory": 0,
        "of_another_organisation": 0,
        "not_established": 0,
    }
    for app_id, principal in by_app.items():
        if app_id in registered:
            continue
        own = _observed(
            _fact(principal, "service_principal", "owned_by_this_directory")
        )
        elsewhere[
            "not_established"
            if own is None
            else "of_this_directory"
            if own
            else "of_another_organisation"
        ] += 1

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
            "can_sign_in_here",
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
        "service_principals": (
            {
                "in_the_evidence": len(principals),
                "with_a_registration_here": len(registered & set(by_app)),
                "without_a_registration_here": elsewhere,
            }
            if principals
            else {"state": "not-collected"}
        ),
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
        "sources": _sources(
            [applications[key] for key in sorted(applications)]
            + [principals[key] for key in sorted(principals)]
        ),
    }


#: How Microsoft Graph names the three states of a policy, and what each means
#: for a sign-in. Source: the `state` property of conditionalAccessPolicy.
CA_STATES = {
    "enabled": "enforced",
    "enabledForReportingButNotEnforced": "report-only",
    "disabled": "off",
}

#: Conditions other than who, by the property that carries each. A policy that
#: sets one applies to fewer sign-ins than its user scope suggests.
CA_NARROWING = (
    "applications",
    "locations",
    "platforms",
    "clientAppTypes",
    "signInRiskLevels",
    "userRiskLevels",
    "devices",
    "servicePrincipalRiskLevels",
    "authenticationFlows",
    "insiderRiskLevels",
)


def _narrowing(conditions: dict) -> list[str]:
    """Which conditions besides the user scope this policy actually sets.

    `applications` set to All and `clientAppTypes` set to all narrow nothing
    and are not listed; anything else that carries a value is.
    """
    found = []
    for name in CA_NARROWING:
        value = conditions.get(name)
        if value in (None, [], {}):
            continue
        if name == "clientAppTypes" and value == ["all"]:
            continue
        if name == "applications" and isinstance(value, dict):
            include = value.get("includeApplications") or []
            rest = any(value.get(key) for key in value if key != "includeApplications")
            if include == ["All"] and not rest:
                continue
        found.append(name)
    return found


def ca_coverage(documents: list[dict], policy_id: str | None = None) -> dict:
    """Who each Conditional Access policy names, read from its own definition.

    THIS IS THE STATIC SCOPE, AND IT IS NOT WHO A POLICY APPLIES TO. A policy
    reaches a sign-in only when every condition holds at that moment, groups
    are resolved by the service at sign-in, and several policies combine.
    None of that is in a definition. What is: whether the policy is enforced,
    whom it names, whom it leaves out, and which other conditions narrow it.
    """
    policies, duplicated = _latest(
        [
            d
            for d in documents
            if (d.get("resource") or {}).get("type") == "conditional-access-policy"
        ]
    )
    refused = [
        d
        for d in documents
        if (d.get("resource") or {}).get("type") == "tenant"
        and isinstance((d.get("facts") or {}).get("conditional_access_policies"), dict)
        and "state" in d["facts"]["conditional_access_policies"]
    ]
    rows = []
    for key in sorted(policies):
        if policy_id and key != policy_id:
            continue
        document = policies[key]
        policy = _observed(_fact(document, "conditional_access_policies", "policy"))
        row: dict[str, Any] = {
            "native_id": key,
            "name": (document.get("resource") or {}).get("display_name") or "",
            "collected_at": (document.get("provenance") or {}).get("collected_at"),
        }
        if not isinstance(policy, dict):
            row.update(
                in_force=NOT_ESTABLISHED,
                static_scope=NOT_ESTABLISHED,
                because="the definition of this policy was not read",
            )
            rows.append(row)
            continue
        state = policy.get("state")
        conditions = policy.get("conditions") or {}
        users = conditions.get("users") or {}
        include = users.get("includeUsers") or []
        everyone = "All" in include
        named = [
            u for u in include if u not in ("All", "None", "GuestsOrExternalUsers")
        ]
        excluded = {
            "users": len(users.get("excludeUsers") or []),
            "groups": len(users.get("excludeGroups") or []),
            "roles": len(users.get("excludeRoles") or []),
        }
        included = {
            "users": len(named),
            "groups": len(users.get("includeGroups") or []),
            "roles": len(users.get("includeRoles") or []),
        }
        guests = "GuestsOrExternalUsers" in include or bool(
            users.get("includeGuestsOrExternalUsers")
        )
        narrowing = _narrowing(conditions)
        if everyone:
            scope = "every user"
        elif any(included.values()) or guests:
            scope = "named principals"
        else:
            scope = "nobody"
        if any(excluded.values()):
            scope += ", with exclusions"
        row.update(
            in_force=CA_STATES.get(str(state), NOT_ESTABLISHED),
            policy_state=state,
            static_scope=scope,
            includes_users=included["users"],
            includes_groups=included["groups"],
            includes_roles=included["roles"],
            includes_guests=guests,
            excludes_users=excluded["users"],
            excludes_groups=excluded["groups"],
            excludes_roles=excluded["roles"],
            narrowed_by=", ".join(narrowing) or "nothing else",
            controls=", ".join(
                (policy.get("grantControls") or {}).get("builtInControls") or []
            )
            or "none listed",
        )
        row["because"] = (
            "the policy's own definition"
            if row["in_force"] != NOT_ESTABLISHED
            else f"{state!r} is not a policy state this engine has a documented "
            "meaning for"
        )
        rows.append(row)

    by_force: dict[str, int] = {}
    for row in rows:
        by_force[row["in_force"]] = by_force.get(row["in_force"], 0) + 1

    not_established = [
        "whether a policy applies to a given sign-in: that depends on every "
        "condition at that moment, and a definition is not a sign-in",
        "who is in a group or holds a role a policy names: no group or role "
        "was expanded, so a count of groups is not a count of people",
        "what several policies do together: they combine at sign-in, and this "
        "reads each on its own",
        "whether anybody is left outside every policy: that needs every "
        "user and every membership, which were not read",
    ]
    if refused:
        not_established.insert(
            0,
            "the policies themselves: the read was refused, so an empty list "
            "here is not a tenant with no policy",
        )
    if policy_id and not rows:
        not_established.insert(
            0, f"policy {policy_id}: no policy with that id is in this evidence"
        )
    used = [policies[key] for key in sorted(policies)] + refused
    return {
        "$schema": SCHEMA,
        "scenario": "ca-coverage",
        "scope": "entra",
        "question": (
            "Whom does each Conditional Access policy name, whom does it leave "
            "out, and is it enforced?"
        ),
        "parameters": {"policy_id": policy_id},
        "columns": [
            "name",
            "native_id",
            "in_force",
            "static_scope",
            "includes_users",
            "includes_groups",
            "includes_roles",
            "includes_guests",
            "excludes_users",
            "excludes_groups",
            "excludes_roles",
            "narrowed_by",
            "controls",
        ],
        "relations": [
            "policy -> the principals its definition names, by identifier",
            "group or role -> its members: NOT JOINED. Nothing was expanded",
        ],
        "rows": rows,
        "policies": {
            "in_the_evidence": len(policies),
            "shown": len(rows),
            "by_in_force": dict(sorted(by_force.items())),
            "read_refused": bool(refused),
        },
        "duplicates": duplicated,
        "not_established": not_established,
        "sources": _sources(used),
    }


_GUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def _only_the_owners_of(group_administrators: list, group_id: str) -> bool:
    """Whether every group among a site's administrators is the owners claim
    of this one Microsoft 365 group.

    SharePoint names the owners of a group as a claim carrying the group's
    identifier followed by `_o`; the same identifier with no suffix is its
    members. Anything else -- another group, the members claim, a security
    group, a principal with no identifier -- is a group this cannot expand,
    and one of those is enough to leave the site as it was.
    """
    if not group_administrators:
        return False
    for entry in group_administrators:
        claim = str((entry or {}).get("principal_id") or "").lower()
        found = _GUID.findall(claim)
        if found != [group_id.lower()] or not claim.endswith(f"{group_id.lower()}_o"):
            return False
    return True


class NotComparable(Exception):
    """Two inspections that do not answer the same question."""


def difference(before: dict, after: dict) -> dict:
    """What changed between two inspections of the same question.

    ONLY LIKE WITH LIKE. Two inspections are compared when they are the same
    scenario with the same parameters; a threshold that moved between them
    would show every row changing for a reason that is not in the tenant, so
    that is refused and not reported as change.

    A ROW THAT IS GONE IS NOT A RESOURCE THAT WAS DELETED. It is a resource
    that is not in the later evidence: removed, or no longer shown to the
    identity that collected, or not collected that time. The comparison says
    it left the evidence and says no more.
    """
    for name in ("scenario", "parameters"):
        if before.get(name) != after.get(name):
            raise NotComparable(
                f"the two inspections differ in {name}: "
                f"{before.get(name)!r} and {after.get(name)!r}. Comparing them "
                "would report the difference in the question as a change in "
                "the tenant."
            )
    columns = [
        c
        for c in (after.get("columns") or list(COLUMNS))
        if c not in ("name", "url", "because")
    ]
    earlier = {row["native_id"]: row for row in before.get("rows", [])}
    later = {row["native_id"]: row for row in after.get("rows", [])}

    def shown(row: dict) -> dict:
        return {"native_id": row["native_id"], "name": row.get("name") or ""}

    changed = []
    for key in sorted(set(earlier) & set(later)):
        moved = {
            column: {
                "before": earlier[key].get(column),
                "after": later[key].get(column),
            }
            for column in columns
            if earlier[key].get(column) != later[key].get(column)
        }
        if moved:
            changed.append({**shown(later[key]), "changed": moved})
    return {
        "$schema": SCHEMA,
        "scenario": after.get("scenario"),
        "comparison": True,
        "parameters": after.get("parameters"),
        "question": after.get("question"),
        "before": before.get("sources"),
        "after": after.get("sources"),
        "same_evidence": (before.get("sources") or {}).get("digest")
        == (after.get("sources") or {}).get("digest"),
        "entered": [shown(later[key]) for key in sorted(set(later) - set(earlier))],
        "left": [shown(earlier[key]) for key in sorted(set(earlier) - set(later))],
        "changed": changed,
        "unchanged": len(set(earlier) & set(later)) - len(changed),
        "not_established": [
            "why a row left: it is not in the later evidence, which is not "
            "the same as the resource no longer existing",
            "what happened between the two collections: two readings are two "
            "moments, and a value that changed and changed back is not seen",
            "when anything changed: only that it differs between the two "
            "collection times recorded above",
        ],
    }


def difference_as_text(result: dict) -> str:
    lines = [f"What changed: {result['question']}", ""]
    for label, sources in (("before", result["before"]), ("after", result["after"])):
        sources = sources or {}
        lines.append(
            f"  {label:<7}{sources.get('documents', 0)} documents, collected "
            f"{sources.get('collected_from')} to {sources.get('collected_to')}"
        )
    if result["same_evidence"]:
        lines += ["", "Both were made from the same evidence: nothing can differ."]
    lines.append("")
    for title, key in (
        ("Entered the evidence", "entered"),
        ("Left the evidence", "left"),
    ):
        lines.append(f"{title}: {len(result[key])}")
        lines += [f"  {row['name'] or row['native_id']}" for row in result[key]]
    lines.append(f"Changed: {len(result['changed'])}")
    for row in result["changed"]:
        lines.append(f"  {row['name'] or row['native_id']}")
        for column, moved in row["changed"].items():
            lines.append(f"    {column}: {moved['before']} -> {moved['after']}")
    lines.append(f"Unchanged: {result['unchanged']}")
    lines += ["", "Not established by this comparison:"]
    lines += [f"  - {item}" for item in result["not_established"]]
    lines.append("")
    return "\n".join(lines)


#: Scenario name -> (what it answers, the function, the collections it reads).
SCENARIOS: dict[str, tuple[str, Callable[[list[dict]], dict], tuple[str, ...]]] = {
    "external-access": (
        "which SharePoint sites permit sharing outside the organisation",
        external_access,
        ("sites-sharing", "tenant-sharing", "guests", "sites-guests"),
    ),
    "app-exposure": (
        "which applications hold a credential that has ended or is about to",
        app_exposure,
        ("applications", "service-principals"),
    ),
    "ca-coverage": (
        "whom each Conditional Access policy names, leaves out, and whether "
        "it is enforced",
        ca_coverage,
        ("conditional-access",),
    ),
    "ownership": (
        "which SharePoint sites name enough administrators, and which cannot say",
        ownership,
        ("sites-owners", "sites", "groups"),
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
    "guests_met",
    "because",
)


def as_table(inspection: dict) -> tuple[list[str], list[list[str]]]:
    columns = list(inspection.get("columns") or COLUMNS)
    rows = [
        [str(row.get(column, "")) for column in columns] for row in inspection["rows"]
    ]
    return columns, rows


def _row_lines(inspection: dict, row: dict) -> list[str]:
    if inspection["scenario"] == "ca-coverage":
        if row["static_scope"] == NOT_ESTABLISHED:
            return [f"  in force         {row['in_force']}  ({row['because']})"]
        return [
            f"  id               {row['native_id']}",
            f"  in force         {row['in_force']}  (state: {row['policy_state']})",
            f"  static scope     {row['static_scope']}",
            f"  includes         users {row['includes_users']} · groups "
            f"{row['includes_groups']} · roles {row['includes_roles']} · guests "
            f"{'yes' if row['includes_guests'] else 'no'}",
            f"  excludes         users {row['excludes_users']} · groups "
            f"{row['excludes_groups']} · roles {row['excludes_roles']}",
            f"  narrowed by      {row['narrowed_by']}",
            f"  controls         {row['controls']}",
        ]
    if inspection["scenario"] == "app-exposure":
        return [
            f"  standing         {row['standing']}  ({row['because']})",
            f"  credentials      ended {row['ended'] if row['ended'] != '' else '-'}"
            f" · ending {row['ending'] if row['ending'] != '' else '-'}"
            f" · later {row['later'] if row['later'] != '' else '-'}"
            f" · earliest end {row['earliest_end'] or '-'}",
            f"  can sign in here {row.get('can_sign_in_here', '[not-collected]')}",
            f"  asks for         application "
            f"{row['requested_application_permissions']} · delegated "
            f"{row['requested_delegated_permissions']}  (asked, not granted)",
        ]
    if inspection["scenario"] == "ownership":
        named = row["named_administrators"]
        groups = row["group_administrators"]
        group_owners = row.get("group_user_owners", "")
        return [
            f"  standing         {row['standing']}  ({row['because']})",
            f"  administrators   read: {row['owners_read']} · named "
            f"{'-' if named == '' else named} · groups "
            f"{'-' if groups == '' else groups}",
            *(
                [
                    f"  people           at least "
                    f"{row['administrators_at_least']}, at most "
                    f"{row['administrators_at_most']}"
                ]
                if row.get("administrators_at_least", "") != ""
                else []
            ),
            f"  Microsoft 365 group  {row.get('connected_group', '[not-collected]')}"
            + (
                f" · owners that are users {group_owners}" if group_owners != "" else ""
            ),
        ]
    return [
        f"  in force         {row['in_force']}  ({row['because']})",
        f"  site / org       {row['site_capability']} / "
        f"{row['organisation_capability']}",
        f"  external sharing {row['external_sharing']} · new guests "
        f"{row['new_guests']} · anonymous links {row['anonymous_links']}",
        f"  guests met       {row.get('guests_met', '[not-collected]')}",
    ]


def as_text(inspection: dict) -> str:
    lines = [inspection["question"], ""]
    counted = (
        inspection.get("sites")
        or inspection.get("applications")
        or inspection.get("policies")
        or {}
    )
    noun = (
        "application"
        if "applications" in inspection
        else "Conditional Access policy"
        if "policies" in inspection
        else "SharePoint site"
    )
    if not inspection["rows"] and not counted.get("in_the_evidence"):
        lines += [f"No {noun} is in this evidence.", ""]
    elif not inspection["rows"]:
        lines += ["Nothing in this evidence matches what was asked for.", ""]
    for row in inspection["rows"]:
        title = row["name"] or row["native_id"]
        lines.append(f"{title}  {row.get('url') or row.get('app_id') or ''}".rstrip())
        lines += _row_lines(inspection, row)
        lines.append("")
    plural = "Conditional Access policies" if noun.endswith("policy") else f"{noun}s"
    lines.append(f"{counted.get('in_the_evidence', 0)} {plural} in the evidence:")
    for state, number in (counted.get("by_in_force") or {}).items():
        lines.append(f"  {state}: {number}")
    for state, number in (counted.get("by_external_sharing") or {}).items():
        lines.append(f"  external sharing {state}: {number}")
    for state, number in (counted.get("by_standing") or {}).items():
        lines.append(f"  {state}: {number}")
    if inspection["duplicates"]:
        lines.append(
            f"  {len(inspection['duplicates'])} sites were in the evidence more "
            "than once; the latest read of each was used"
        )
    principals = inspection.get("service_principals") or {}
    if "in_the_evidence" in principals:
        without = principals["without_a_registration_here"]
        lines += [
            "",
            f"{principals['in_the_evidence']} service principals in the evidence:",
            f"  with a registration here {principals['with_a_registration_here']}",
            f"  without one: of another organisation "
            f"{without['of_another_organisation']} · of this directory "
            f"{without['of_this_directory']} · not established "
            f"{without['not_established']}",
        ]
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
    met = directory.get("met_by_sites")
    if met:
        lines += [
            "",
            "Guest accounts the sites have met, by directory object id:",
            f"  distinct accounts {met['distinct_guest_accounts']}",
        ]
        if met["also_listed_as_guests"] is not None:
            lines += [
                f"  also listed as guests in the directory "
                f"{met['also_listed_as_guests']} · not listed as guests "
                f"{met['not_listed_as_guests']}",
                f"  listed as guests and met by no site "
                f"{met['listed_and_met_by_no_site']}",
            ]
        lines.append(
            "  A site having met an account is not that account having access."
        )
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
