#!/usr/bin/env python3
"""Regenerate the tenant-governance fixtures from the collector itself.

A FIXTURE WRITTEN BY HAND IS A SECOND IMPLEMENTATION OF THE COLLECTOR. It
starts identical, and it stops being identical the first time the collector
learns a field -- at which point the rules are being tested against a shape the
engine no longer produces, and the tests still pass. So these are produced by
running the real `collect()` against a transport that answers with the objects
Microsoft's own reference documents, and the only thing written here is what
that transport says.

WHAT THE TRANSPORT IS ALLOWED TO SAY. Every object below is the documented
shape of the resource, with values chosen to put a rule on each side of its
condition. Nothing was observed in a tenant, and no fixture here claims it was:
`acquisition` says `collected` because that is what the collector writes, and
what proves a live read is the live-proof record, not a file in this directory.

    python tools/tenant-governance-fixtures.py
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from m365_governance import tenant_governance  # noqa: E402
from m365_governance.graph import GraphReader  # noqa: E402

OUT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src/m365_governance/data/fixtures/entra"
)

TENANT = "https://contoso-admin.sharepoint.com"
OBSERVED_AT = "2026-08-23T09:00:00Z"

ROLES = "roleAssignments"
POLICY = "authorizationPolicy"

#: The authorization policy as Microsoft's reference documents it, with the
#: default-user-role block filled in. Two variants differ only in values.
def policy(**over):
    default = {
        "allowedToCreateApps": True,
        "allowedToCreateSecurityGroups": True,
        "allowedToCreateTenants": True,
        "allowedToReadOtherUsers": True,
        "allowedToReadBitlockerKeysForOwnedDevice": True,
        "permissionGrantPoliciesAssigned": [
            "ManagePermissionGrantsForSelf.microsoft-user-default-legacy"
        ],
    }
    default.update(over.pop("defaultUserRolePermissions", {}))
    body = {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#policies/authorizationPolicy/$entity",
        "id": "authorizationPolicy",
        "displayName": "Authorization Policy",
        "description": "Used to manage authorization related settings across the company.",
        "allowInvitesFrom": "everyone",
        "allowUserConsentForRiskyApps": False,
        "allowEmailVerifiedUsersToJoinOrganization": True,
        "allowedToSignUpEmailBasedSubscriptions": True,
        "allowedToUseSSPR": True,
        "blockMsolPowerShell": False,
        "guestUserRoleId": "10dae51f-b6af-4016-8d66-8c2a99b929b3",
        "defaultUserRolePermissions": default,
    }
    body.update(over)
    return body


def assignment(n: int, *, synced=None, service_principal=False):
    """One role assignment, and the principal it points at.

    THE ASSIGNMENT CARRIES AN IDENTIFIER AND NOTHING ELSE, because that is what
    the collector asks for. The account itself is answered separately, by the
    transport below, with the two fields the collector selected -- so a display
    name has nowhere to appear even in a fixture.
    """
    kind = "sp" if service_principal else "user"
    return (
        {
            "id": f"assignment-{n}",
            "principalId": f"{kind}-{n:04d}-0000-4000-8000-00000000000{n}",
            "directoryScopeId": "/",
        },
        synced,
    )


def token() -> str:
    body = {
        "tid": "c0ffee00-0000-4000-8000-000000000001",
        "roles": ["Policy.Read.All", "RoleManagement.Read.Directory"],
    }
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def routed(*, roles, authorization):
    """A transport that answers the three shapes this collector asks for.

    The principal probe is the interesting one: it answers `404` for anything
    that is not a user, which is how the collector tells a service principal
    from a person without ever asking what either is called.
    """
    accounts = {a["principalId"]: synced for a, synced in roles}

    def transport(url, _token):
        if ROLES in url:
            return (200, json.dumps({"value": [a for a, _ in roles]}), {})
        if "/users/" in url:
            principal = url.split("/users/")[1].split("?")[0]
            if not principal.startswith("user-"):
                return (404, json.dumps({"error": {"code": "Request_ResourceNotFound"}}), {})
            body = {"id": principal}
            if accounts[principal] is not ...:
                body["onPremisesSyncEnabled"] = accounts[principal]
            return (200, json.dumps(body), {})
        if POLICY in url:
            return (200, json.dumps(authorization), {})
        raise AssertionError(f"nothing was configured for {url}")

    return transport


#: name -> (role assignments, authorization policy). Each entry exists to put
#: at least one rule on a side of its condition it is not otherwise on.
CASES = {
    "entra-authorization-policy-open-defaults": (
        [assignment(1, synced=None), assignment(2, synced=None)],
        policy(allowUserConsentForRiskyApps=True),
    ),
    "entra-authorization-policy-restrained": (
        [assignment(1, synced=None), assignment(2, synced=None)],
        policy(
            allowInvitesFrom="adminsAndGuestInviters",
            allowUserConsentForRiskyApps=False,
            defaultUserRolePermissions={
                "allowedToCreateApps": False,
                "allowedToCreateTenants": False,
                "permissionGrantPoliciesAssigned": [],
            },
        ),
    ),
    # Microsoft's own reference says, in capitals, do not set this to false.
    "entra-authorization-policy-directory-unreadable": (
        [assignment(1, synced=None), assignment(2, synced=None)],
        policy(
            allowInvitesFrom="adminsAndGuestInviters",
            defaultUserRolePermissions={
                "allowedToReadOtherUsers": False,
                "allowedToCreateApps": False,
                "allowedToCreateTenants": False,
                "permissionGrantPoliciesAssigned": [],
            },
        ),
    ),
    "entra-global-administrators-too-many": (
        [assignment(n, synced=None) for n in range(1, 8)],
        policy(allowInvitesFrom="adminsAndGuestInviters"),
    ),
    "entra-global-administrators-single-account": (
        [assignment(1, synced=None)],
        policy(allowInvitesFrom="adminsAndGuestInviters"),
    ),
    "entra-global-administrators-all-synced": (
        [assignment(n, synced=True) for n in range(1, 4)],
        policy(allowInvitesFrom="adminsAndGuestInviters"),
    ),
    "entra-global-administrators-healthy": (
        [
            assignment(1, synced=None),
            assignment(2, synced=None),
            assignment(3, synced=True),
            assignment(4, service_principal=True),
        ],
        policy(allowInvitesFrom="adminsAndGuestInviters"),
    ),
}

#: Which area's document each fixture keeps. A collection produces one document
#: per area; a fixture is one document, and the name says which one it is.
KEEPS = {
    "privileged-role-summary": "global-administrators",
    "authorization-policy": "authorization-policy",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (roles, authorization) in CASES.items():
        reader = GraphReader(
            token(),
            transport=routed(roles=roles, authorization=authorization),
            sleep=lambda _: None,
        )
        collected = tenant_governance.collect(reader, TENANT, OBSERVED_AT)
        wanted = (
            "privileged-role-summary"
            if "global-administrators" in name
            else "authorization-policy"
        )
        document = next(
            d for d in collected.documents if d["resource"]["type"] == wanted
        )
        path = OUT / f"{name}.json"
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written.append(path.name)
    print("\n".join(sorted(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
