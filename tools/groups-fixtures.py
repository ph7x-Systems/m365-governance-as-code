#!/usr/bin/env python3
"""Produce the groups fixtures by running the collector over a stand-in
service, so that a change to the collector changes them and a test notices."""

from __future__ import annotations

import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import groups  # noqa: E402
from m365_governance.graph import GraphReader  # noqa: E402

OUT = ROOT / "src" / "m365_governance" / "data" / "fixtures" / "entra"
TENANT = "https://contoso-admin.sharepoint.com"
OBSERVED_AT = "2026-11-12T10:00:00Z"
USER = "#microsoft.graph.user"
PRINCIPAL = "#microsoft.graph.servicePrincipal"


def token() -> str:
    body = {
        "tid": "c0ffee00-0000-4000-8000-000000000001",
        "roles": ["GroupMember.Read.All"],
    }
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def group(number: int, name: str, *, team: bool = False) -> dict:
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "displayName": name,
        "createdDateTime": "2025-02-01T09:00:00Z",
        "visibility": "Private",
        "resourceProvisioningOptions": ["Team"] if team else [],
    }


def people(*kinds: str) -> list[dict]:
    return [
        {"@odata.type": kind, "id": f"00000000-0000-4000-9000-{n:012d}"}
        for n, kind in enumerate(kinds)
    ]


GROUPS = [group(1, "Finance", team=True), group(2, "Projects"), group(3, "Archive")]
OWNERS = {
    GROUPS[0]["id"]: people(USER, USER),
    GROUPS[1]["id"]: people(USER),
    GROUPS[2]["id"]: people(PRINCIPAL),
}
MEMBERS = {
    GROUPS[0]["id"]: people(USER, USER, USER, USER),
    GROUPS[1]["id"]: people(USER, USER),
    GROUPS[2]["id"]: [],
}


def answering(url, _token):
    for identifier in OWNERS:
        if f"/groups/{identifier}/owners" in url:
            return (200, json.dumps({"value": OWNERS[identifier]}), {})
        if f"/groups/{identifier}/members" in url:
            return (200, json.dumps({"value": MEMBERS[identifier]}), {})
    return (200, json.dumps({"value": GROUPS}), {})


def refusing(_url, _token):
    body = {
        "error": {
            "code": "Authorization_RequestDenied",
            "message": "Insufficient privileges to complete the operation.",
        }
    }
    return (403, json.dumps(body), {})


CASES = {
    "entra-groups-three-listed": (answering, "tenant"),
    "entra-group-single-owner": (answering, GROUPS[1]["id"]),
    "entra-groups-refused": (refusing, "tenant"),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (transport, keeps) in CASES.items():
        reader = GraphReader(token(), transport=transport, sleep=lambda _: None)
        collected = groups.collect(reader, TENANT, OBSERVED_AT)
        document = next(
            d
            for d in collected.documents
            if d["resource"]["type"] == keeps or d["resource"]["native_id"] == keeps
        )
        (OUT / f"{name}.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
