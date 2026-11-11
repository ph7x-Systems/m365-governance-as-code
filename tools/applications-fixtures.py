#!/usr/bin/env python3
"""Produce the applications fixtures by running the collector over a stand-in
service, so that a change to the collector changes them and a test notices."""

from __future__ import annotations

import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import applications  # noqa: E402
from m365_governance.graph import GraphReader  # noqa: E402

OUT = ROOT / "src" / "m365_governance" / "data" / "fixtures" / "entra"
TENANT = "https://contoso-admin.sharepoint.com"
OBSERVED_AT = "2026-11-11T10:00:00Z"


def token() -> str:
    body = {
        "tid": "c0ffee00-0000-4000-8000-000000000001",
        "roles": ["Application.Read.All"],
    }
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def registration(number: int, name: str, *, secrets=(), certificates=(), asks=()):
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "appId": f"00000000-0000-4000-9000-{number:012d}",
        "displayName": name,
        "createdDateTime": "2025-03-01T09:00:00Z",
        "signInAudience": "AzureADMyOrg",
        "passwordCredentials": [
            {
                "keyId": f"00000000-0000-4000-a000-{index:012d}",
                "hint": "abc",
                "displayName": "created by hand",
                "startDateTime": "2025-12-01T00:00:00Z",
                "endDateTime": ends,
            }
            for index, ends in enumerate(secrets)
        ],
        "keyCredentials": [
            {
                "keyId": f"00000000-0000-4000-b000-{index:012d}",
                "customKeyIdentifier": "00FF",
                "type": "AsymmetricX509Cert",
                "usage": "Verify",
                "startDateTime": "2025-12-01T00:00:00Z",
                "endDateTime": ends,
            }
            for index, ends in enumerate(certificates)
        ],
        "requiredResourceAccess": [
            {
                "resourceAppId": "00000003-0000-0000-c000-000000000000",
                "resourceAccess": [
                    {"id": f"00000000-0000-4000-c000-{i:012d}", "type": kind}
                    for i, kind in enumerate(asks)
                ],
            }
        ],
    }


THREE = [
    registration(
        1, "Payroll export", secrets=("2026-11-25T00:00:00Z",), asks=("Role",)
    ),
    registration(
        2,
        "Intranet search",
        certificates=("2027-06-01T00:00:00Z",),
        asks=("Scope", "Scope"),
    ),
    registration(3, "Retired connector", secrets=("2026-01-15T00:00:00Z",)),
]


def answering(status: int, body: dict):
    def transport(_url, _token):
        return (status, json.dumps(body), {})

    return transport


CASES = {
    "entra-applications-three-registered": (answering(200, {"value": THREE}), "tenant"),
    "entra-application-secret-ending": (
        answering(200, {"value": THREE}),
        THREE[0]["id"],
    ),
    "entra-applications-refused": (
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
        collected = applications.collect(reader, TENANT, OBSERVED_AT)
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
