#!/usr/bin/env python3
"""Produce the service principal fixtures by running the collector over a
stand-in service, so that a change to the collector changes them."""

from __future__ import annotations

import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import service_principals  # noqa: E402
from m365_governance.graph import GraphReader  # noqa: E402

OUT = ROOT / "src" / "m365_governance" / "data" / "fixtures" / "entra"
TENANT = "https://contoso-admin.sharepoint.com"
OBSERVED_AT = "2026-11-12T10:00:00Z"
HOME = "c0ffee00-0000-4000-8000-000000000001"
ELSEWHERE = "f8cdef31-a31e-4b4a-93e4-5f571e91255a"


def token() -> str:
    body = {"tid": HOME, "roles": ["Application.Read.All"]}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def principal(number: int, name: str, owner: str, *, enabled=True, secrets=()):
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "appId": f"00000000-0000-4000-9000-{number:012d}",
        "displayName": name,
        "servicePrincipalType": "Application",
        "accountEnabled": enabled,
        "appOwnerOrganizationId": owner,
        "passwordCredentials": [
            {"hint": "abc", "startDateTime": "2025-12-01T00:00:00Z", "endDateTime": e}
            for e in secrets
        ],
        "keyCredentials": [],
    }


THREE = [
    principal(1, "Payroll export", HOME, secrets=("2026-11-25T00:00:00Z",)),
    principal(2, "A vendor's connector", ELSEWHERE),
    principal(3, "Retired connector", HOME, enabled=False),
]


def answering(status: int, body: dict):
    def transport(_url, _token):
        return (status, json.dumps(body), {})

    return transport


CASES = {
    "entra-service-principals-three-listed": (
        answering(200, {"value": THREE}),
        "tenant",
    ),
    "entra-service-principal-of-another-organisation": (
        answering(200, {"value": THREE}),
        THREE[1]["id"],
    ),
    "entra-service-principals-refused": (
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
        collected = service_principals.collect(reader, TENANT, OBSERVED_AT)
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
