"""The collector has no write path, and does not conclude.

A static check rather than a run: there is no tenant in CI, and there never
will be. What can be proved offline is that the script cannot change anything
and does not smuggle a judgement into the evidence.

Every check here walks **every** PowerShell file under the collectors
directory. It used to name one path, which was true when there was one file
and would have quietly stopped proving anything about the rest the moment the
collector was split into modules. See docs/POWERSHELL-STANDARDS.md.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from conftest import DATA

COLLECTORS = DATA / "collectors"
COLLECTOR = COLLECTORS / "powershell" / "sharepoint" / "Get-SpoEvidence.ps1"

#: Every `.ps1` and `.psm1` that ships. Sorted so a failure names the same file
#: on every machine.
POWERSHELL = sorted(p for p in COLLECTORS.rglob("*") if p.suffix in {".ps1", ".psm1"})

#: Verb-Noun forms that change something. Matched on the PnP and Graph command
#: surfaces, where a mutation is always one of these verbs.
MUTATING = re.compile(
    r"\b(Set|New|Remove|Add|Update|Grant|Revoke|Reset|Restore|Move|Rename|"
    r"Disable|Enable|Submit|Publish)-(PnP|Mg|SPO)\w+",
    re.IGNORECASE,
)

#: Fields that presume a rule. A collector that returns any of these has moved
#: the judgement out of a reviewable diff and into code.
CONCLUSIONS = (
    "is_compliant",
    "isCompliant",
    "risk",
    "score",
    "recommended_action",
    "recommendation",
    "severity",
)

FUNCTION = re.compile(r"^function\s+([A-Za-z]+)-(\w+)", re.MULTILINE)


def source() -> str:
    return COLLECTOR.read_text(encoding="utf-8")


def body(path) -> str:
    """The file without its leading comment block, which names the forbidden
    words precisely in order to forbid them."""
    text = path.read_text(encoding="utf-8")
    return text.split("#>", 1)[1] if "#>" in text else text


def test_the_collector_exists():
    assert COLLECTOR.is_file()


def test_every_powershell_file_is_checked():
    """A guard on the guards. If this list were ever empty — a moved
    directory, a renamed suffix — every check below would pass by walking
    nothing."""
    assert POWERSHELL
    assert COLLECTOR in POWERSHELL


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_no_powershell_file_has_a_write_path(path):
    found = MUTATING.findall(path.read_text(encoding="utf-8"))
    assert not found, f"mutating cmdlet in a read-only collector: {found}"


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_no_powershell_file_returns_a_conclusion(path):
    offenders = [word for word in CONCLUSIONS if word in body(path)]
    assert not offenders, f"a collector may not decide: {offenders}"


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_every_powershell_file_fails_loudly(path):
    """`Set-StrictMode` turns a misspelled property into an error instead of
    into a `$null` that reaches an evidence envelope looking like an observed
    absence. `Stop` keeps a failed read from being walked past."""
    text = path.read_text(encoding="utf-8")
    assert "Set-StrictMode -Version Latest" in text
    assert "$ErrorActionPreference = 'Stop'" in text


@pytest.mark.parametrize("path", POWERSHELL, ids=lambda p: p.name)
def test_every_function_uses_an_approved_verb(path):
    """Microsoft's list, read from the installed PowerShell rather than
    copied here, so it cannot go stale against the runtime that will load
    these files.

    https://learn.microsoft.com/powershell/scripting/developer/cmdlet/approved-verbs-for-windows-powershell-commands
    """
    if not shutil.which("pwsh"):
        pytest.skip("pwsh is not installed; only collection needs it")

    approved = set(
        subprocess.run(
            ["pwsh", "-NoProfile", "-Command", "(Get-Verb).Verb"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    used = {verb for verb, _ in FUNCTION.findall(path.read_text(encoding="utf-8"))}
    assert used <= approved, f"unapproved verb: {sorted(used - approved)}"


def test_the_collector_records_identity_kind():
    """Without it, a delegated run reads as a tenant-wide statement."""
    assert any("identity_kind" in p.read_text(encoding="utf-8") for p in POWERSHELL)


def test_the_collector_never_returns_an_empty_list_on_failure():
    """Every failure path must produce a state and a reason, not `@()`."""
    joined = "".join(body(p) for p in POWERSHELL)
    assert "New-Unavailable" in joined
    assert re.search(r"catch\s*\{[^}]*Resolve-FailureState", joined, re.DOTALL)


def test_group_expansion_is_declared_incomplete_rather_than_guessed():
    joined = "".join(p.read_text(encoding="utf-8") for p in POWERSHELL)
    assert "not-attempted" in joined
    assert "minimum_count" in joined


def test_a_slice_with_no_site_connects_to_the_admin_centre():
    """The Python side knows which slices pass a `-SiteUrl`; the PowerShell
    side decides where to connect. Nothing joined the two, and they diverged:
    `TenantSharing` was added to the collector's switch and not to its list of
    admin modes, so the mode asked for a `-SiteUrl` that its own slice never
    passes. It would have failed on the first tenant run and on no test.
    """
    from m365_governance import collecting

    connection = (COLLECTOR.parent / "modules" / "Connection.psm1").read_text(
        encoding="utf-8"
    )
    declared = re.search(r"\$script:AdminModes\s*=\s*@\(([^)]*)\)", connection)
    assert declared, "Connection.psm1 no longer declares $script:AdminModes"
    admin = set(re.findall(r"'([^']+)'", declared.group(1)))

    siteless = {s.mode for s in collecting.SLICES.values() if not s.needs_site}
    assert siteless <= admin, (
        f"slice modes with no -SiteUrl that would connect to one: "
        f"{sorted(siteless - admin)}"
    )


#: The site properties Microsoft documents as **not populated** by
#: `Get-SPOSite` when `-Limit` or `-Filter` is given: "will not be populated and
#: may contain a default value". `Get-PnPTenantSite` without `-Identity` calls
#: the same filter-based admin API, so the limitation reaches this collector.
#:
#: One of them, `SharingCapability`, was read from that path and was wrong on a
#: tenant on 2026-08-08 — the enum's zero member, with no marker on it. These
#: two tests exist so nobody has to remember that.
#:
#: https://learn.microsoft.com/powershell/module/microsoft.online.sharepoint.powershell/get-sposite
UNPOPULATED_BY_ENUMERATION = frozenset(
    {
        "AllowDownloadingNonWebViewableFiles",
        "AllowEditing",
        "AllowSelfServiceUpgrade",
        "AnonymousLinkExpirationInDays",
        "ConditionalAccessPolicy",
        "DefaultLinkPermission",
        "DefaultLinkToExistingAccess",
        "DefaultSharingLinkType",
        "DenyAddAndCustomizePages",
        "DisableCompanyWideSharingLinks",
        "ExternalUserExpirationInDays",
        "InformationSegment",
        "LimitedAccessFileType",
        "OverrideTenantAnonymousLinkExpirationPolicy",
        "OverrideTenantExternalUserExpirationPolicy",
        "PWAEnabled",
        "SandboxedCodeActivationCapability",
        "SensitivityLabel",
        "SharingAllowedDomainList",
        "SharingBlockedDomainList",
        "SharingCapability",
        "SharingDomainRestrictionMode",
    }
)

#: The one module fed by the enumeration. Every other module receives a site
#: from `Get-PnPTenantSite -Identity` or from `Get-PnPSite`, neither of which
#: the documented limitation describes.
SITES_MODULE = COLLECTORS / "powershell" / "sharepoint" / "modules" / "Sites.psm1"

AUDIT = COLLECTORS.parents[3] / "docs" / "COLLECTION-PATH-AUDIT.md"


def enumerated_map() -> set[str]:
    """The PnP property names `Get-SiteInventoryFacts` maps, read out of the
    hashtable rather than restated here: a list kept by hand would go stale
    exactly when it mattered."""
    text = SITES_MODULE.read_text(encoding="utf-8")
    block = text.split("$map = [ordered]@{", 1)[1].split("}", 1)[0]
    return set(re.findall(r"=\s*'([A-Za-z]+)'", block))


def test_the_enumerated_map_is_read_and_not_empty():
    """If the parse above ever returns nothing, the guard below passes for the
    wrong reason. This is the test that keeps it honest."""
    assert len(enumerated_map()) >= 5


def test_the_enumerated_map_avoids_every_documented_unpopulated_property():
    """Microsoft documents that filtered enumeration may return a default value
    for these instead of the real one, so a fact built on them would be a wrong
    answer with the right type and no marker."""
    forbidden = enumerated_map() & UNPOPULATED_BY_ENUMERATION
    assert not forbidden, (
        f"{sorted(forbidden)} read from the enumeration path, which Get-SPOSite "
        "documents as not populated there. Use Get-PnPTenantSite -Identity."
    )


def test_the_audit_lists_the_same_properties_as_the_guard():
    """The audit prints the twenty-two so a reader can see them. Two copies of
    a list drift; this makes them fail together instead."""
    heading = "### The twenty-two, as documented"
    printed = AUDIT.read_text(encoding="utf-8").split(heading, 1)
    assert len(printed) == 2, "the audit no longer prints the documented list"
    block = printed[1].split("```")[1]
    assert set(block.split()) == set(UNPOPULATED_BY_ENUMERATION)


#: Every resource block the collector writes. Containment is not optional in
#: the schema, so a mode that forgets it produces evidence the engine refuses
#: at runtime, on a tenant, after somebody waited for a collection.
RESOURCE_BLOCK = re.compile(r"id\s*=\s*[^;]+;\s*type\s*=\s*'(\w+)'", re.MULTILINE)


def test_every_resource_the_collector_writes_declares_its_containment():
    """`scope` and `parent` are required by evidence.schema.json.

    A resource without them is a resource whose place in the estate lives in
    prose, which is the thing the model was changed to stop.
    """
    source = COLLECTOR.read_text(encoding="utf-8")
    blocks = [m for m in RESOURCE_BLOCK.finditer(source)]
    assert len(blocks) >= 8, "the resource blocks moved; this test found almost none"

    for match in blocks:
        # The two fields follow the type on the next lines of the same literal.
        window = source[match.end() : match.end() + 220]
        kind = match.group(1)
        assert "scope" in window, f"a {kind} resource is written without a scope"
        assert "parent" in window, f"a {kind} resource is written without a parent"


#: url -> the tenant it belongs to. The admin centre lives on its own host, and
#: recording that host as the tenant meant two modes on one tenant produced two
#: tenant identities: evidence that could never be assembled into one
#: assessment. Microsoft documents the admin form as `{prefix}-admin`.
#:
#: https://learn.microsoft.com/sharepoint/dev/spfx/set-up-your-developer-tenant
TENANT_OF = {
    "https://contoso-admin.sharepoint.com": "contoso.sharepoint.com",
    "https://contoso.sharepoint.com/sites/finance": "contoso.sharepoint.com",
    # Every cloud keeps the shape and changes the suffix, so only the first
    # label is touched.
    "https://contoso-admin.sharepoint.us": "contoso.sharepoint.us",
    # `-admin` is a suffix on the first label and not a substring anywhere.
    "https://admin-portal.sharepoint.com": "admin-portal.sharepoint.com",
    # A KNOWN LIMIT, asserted so it is a decision rather than a surprise: a
    # multi-geo satellite is returned as itself, because the documented mapping
    # covers the admin centre and nothing else. Resolving it needs the
    # directory id, and no collection path for that has been proven yet.
    "https://contoso-emea.sharepoint.com/sites/x": "contoso-emea.sharepoint.com",
}


def test_the_tenant_is_the_tenant_and_not_whatever_was_connected_to():
    if not shutil.which("pwsh"):
        pytest.skip("pwsh is not installed; only collection needs it")

    module = COLLECTOR.parent / "modules" / "Connection.psm1"
    script = f"Import-Module '{module}' -Force; " + "; ".join(
        f"Get-TenantHost -Url '{url}'" for url in TENANT_OF
    )
    answers = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    assert answers == list(TENANT_OF.values())
