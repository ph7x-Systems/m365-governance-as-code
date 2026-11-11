#!/usr/bin/env python3
"""Produce the guests fixtures by running the collector over a stand-in service.

A fixture written by hand agrees with whoever wrote it. These are what the
collector itself writes when the service answers a known way, so a change to
the collector changes them and a test notices.
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import guests  # noqa: E402
from m365_governance.graph import GraphReader  # noqa: E402

OUT = ROOT / "src" / "m365_governance" / "data" / "fixtures" / "entra"
TENANT = "https://contoso-admin.sharepoint.com"
OBSERVED_AT = "2026-11-11T10:00:00Z"


def token() -> str:
    body = {"tid": "c0ffee00-0000-4000-8000-000000000001", "roles": ["User.Read.All"]}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def account(number: int, *, state: str = "Accepted", enabled: bool = True) -> dict:
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "userType": "Guest",
        "accountEnabled": enabled,
        "externalUserState": state,
        "externalUserStateChangeDateTime": "2026-06-01T09:00:00Z",
        "createdDateTime": "2026-05-30T09:00:00Z",
    }


def answering(status: int, body: dict):
    def transport(_url, _token):
        return (status, json.dumps(body), {})

    return transport


THREE = [account(1), account(2, state="PendingAcceptance"), account(3, enabled=False)]

#: name -> (transport, which document the fixture keeps).
CASES = {
    "entra-guests-three-accounts": (answering(200, {"value": THREE}), "tenant"),
    "entra-guest-invitation-pending": (
        answering(200, {"value": THREE}),
        THREE[1]["id"],
    ),
    "entra-guests-refused": (
        answering(
            403,
            {
                "error": {
                    "code": "Authorization_RequestDenied",
                    "message": "Insufficient privileges to complete the operation.",
                }
            },
        ),
        "tenant",
    ),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (transport, keeps) in CASES.items():
        reader = GraphReader(token(), transport=transport, sleep=lambda _: None)
        collected = guests.collect(reader, TENANT, OBSERVED_AT)
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
