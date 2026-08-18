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
from pathlib import Path

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

    # PowerShell slices only. A Graph slice has no `-SiteUrl` to pass and no
    # PnP session to open, so requiring its mode to appear in the collector's
    # admin list would be asking one collector to declare another's work.
    siteless = {
        s.mode
        for s in collecting.SLICES.values()
        if not s.needs_site and s.source == "powershell"
    }
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
RESOURCE_BLOCK = re.compile(r"workload = 'sharepoint'; type = '([a-z]+)'\n")


def test_every_resource_the_collector_writes_declares_its_containment():
    """Containment is not optional in the schema.

    A mode that forgets it produces evidence the engine refuses at runtime, on
    a tenant, after somebody waited for a collection.
    """
    source = COLLECTOR.read_text(encoding="utf-8")
    blocks = list(RESOURCE_BLOCK.finditer(source))
    assert len(blocks) >= 8, "the resource blocks moved; this test found almost none"

    for match in blocks:
        # The remaining fields follow the type on the next lines of the same
        # literal. The window grew when identity became structured: a resource
        # now carries its own native id and tenant before it reaches `scope`.
        window = source[match.end() : match.end() + 420]
        kind = match.group(1)
        for field in ("native_id", "tenant", "scope", "parent"):
            assert field in window, f"a {kind} resource is written without {field}"


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


def test_a_sibling_module_does_not_unload_evidence_from_its_caller():
    """`Import-Module -Force` on an already-loaded module REMOVES it first, and
    the removal reaches the caller's scope.

    Every collector module imports Evidence.psm1. When those nested imports
    carried `-Force`, importing the second module unloaded the Evidence that
    `Get-SpoEvidence.ps1` had just imported, and the orchestrator lost
    `Initialize-Evidence` before it could call it. Every mode failed against
    every tenant with "The term 'Initialize-Evidence' is not recognized",
    which is a shipped collector that cannot collect.

    A source check would have missed the point: this is about what the loaded
    session holds, so the test loads the modules the way the collector does
    and asks the session.
    """
    if not shutil.which("pwsh"):
        pytest.skip("pwsh is not installed; only collection needs it")

    modules = COLLECTOR.parent / "modules"
    ordem = [
        "Evidence",
        "Connection",
        "Sites",
        "Sharing",
        "Permissions",
        "Modernity",
        "Activity",
        "Classification",
        "Spfx",
        "Agents",
    ]
    guiao = (
        "$m = '"
        + str(modules)
        + "'; "
        + "".join(f"Import-Module (Join-Path $m '{n}.psm1') -Force; " for n in ordem)
        + "@('Initialize-Evidence','New-ScalarFact','New-AbsentFact','New-Evidence',"
        "'Write-Evidence','Resolve-FailureState','New-TenantIdentity') "
        "| ForEach-Object { "
        "if (-not (Get-Command $_ -ErrorAction SilentlyContinue)) { $_ } }"
    )
    saida = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", guiao],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert not saida, (
        "importing the collector's modules in its own order left these helpers "
        f"unavailable: {saida}. A nested `Import-Module ... -Force` unloads the "
        "caller's copy; drop the -Force."
    )


def test_no_fixture_claims_an_api_the_collector_never_uses():
    """`source_api` says which path the evidence was read through. It is not
    decoration.

    Twenty-seven fixtures said `Microsoft Graph v1.0`. This collector has
    never gone through Graph: it reads lists with `Get-PnPList` and CSOM
    objects, and `Evidence.psm1` carries `PnP.PowerShell / CSOM` as the
    default. The claim was false and travelled inside evidence documents,
    which is where a false claim costs the most, because it is where the
    product asks to be believed.

    The gate ties every published `source_api` to a collection path this
    product has. A fixture that wants to claim another one has to add it
    here and, before that, to the collector.
    """
    import json

    paths = set()
    modules = COLLECTOR.parent / "modules"
    # The orchestrator declares paths too: the admin one lives there and not
    # in the modules. Reading only the modules produced a gate that accused
    # true evidence.
    for f in [COLLECTOR, *modules.glob("*.psm1")]:
        for m in re.finditer(r"-SourceApi\s+'([^']+)'", f.read_text(encoding="utf-8")):
            paths.add(m.group(1))
    evid = (modules / "Evidence.psm1").read_text(encoding="utf-8")
    default = re.search(r"\[string\]\s*\$SourceApi\s*=\s*'([^']+)'", evid)
    if default:
        paths.add(default.group(1))

    # The second collector. Read from the reader itself rather than written out
    # here, so that a version bump in one place cannot make this gate accuse
    # evidence the product really does produce.
    from m365_governance.graph import VERSION

    paths.add(f"Microsoft Graph {VERSION}")

    assert paths, "the collector declares no collection path at all"

    bad = []
    for p in sorted((DATA / "fixtures").rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for doc in d if isinstance(d, list) else [d]:
            api = (doc.get("provenance") or {}).get("source_api")
            if api and api not in paths:
                bad.append(f"{p.name}: says `{api}`")
    assert not bad, (
        "fixtures claiming an API no collector of this product uses:\n  "
        + "\n  ".join(sorted(set(bad))[:12])
        + f"\n  the paths that exist: {sorted(paths)}"
    )


REGISTRY = DATA / "fixture-registry.json"


def test_every_shipped_fixture_is_classified_once():
    """What a file IS cannot be inferred from its name or its host.

    The product page presented `list-over-limit.json` with `Collected` and a
    date, and it read as a reading taken from a tenant at 14:02. It is a
    construction. The result the Engine produces from it is true; the
    evidence was never observed anywhere, and the difference between those
    two things is what this product sells.
    """
    import json

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = {f["path"]: f for f in doc["fixtures"]}
    on_disk = {str(p.relative_to(DATA)) for p in (DATA / "fixtures").rglob("*.json")}

    assert len(entries) == len(doc["fixtures"]), "the registry repeats a path"
    unclassified = sorted(on_disk - set(entries))
    assert not unclassified, (
        f"shipped fixtures with no classification: {unclassified[:6]}. "
        "Classify them: what a file is cannot be inferred."
    )
    ghosts = sorted(set(entries) - on_disk)
    assert not ghosts, f"the registry names files that do not exist: {ghosts[:6]}"

    for path, f in entries.items():
        assert f["origin"] in ("synthetic", "sanitized-observation", "observed"), path
        assert f.get("purpose"), f"{path}: classified without saying what it is for"
        if f["origin"] == "synthetic":
            assert f["may_be_presented_as_tenant_observation"] is False, (
                f"{path}: it is a construction and it is authorised to pass as "
                "a tenant observation"
            )


def test_the_public_example_is_classified_and_is_a_construction():
    """Named, because it is what the site publishes. If it ever leaves the
    registry or changes classification, this fails by name instead of in
    silence."""
    import json

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    target = "fixtures/sharepoint/list-over-limit.json"
    f = next(
        (x for x in doc["fixtures"] if x["path"].replace("\\", "/") == target),
        None,
    )
    assert f, f"{target} left the registry, and it is the fixture the site publishes"
    assert f["origin"] == "synthetic", (
        f"{target} is classified as {f['origin']}: the host is contoso.sharepoint.com"
    )
    assert f["may_be_presented_as_tenant_observation"] is False


def test_the_evidence_schema_knows_nothing_about_fixtures():
    """`acquisition` answers how REAL evidence reached an Assessment. Adding
    `synthetic` to it would let a production Assessment validate constructed
    evidence, and the contract would stop telling the two apart."""
    import json

    schema = json.loads(
        (DATA / "schemas" / "evidence.schema.json").read_text(encoding="utf-8")
    )
    text = json.dumps(schema)
    assert "synthetic" not in text, (
        "`synthetic` entered the evidence schema. It is repository metadata, "
        "not a way for evidence to arrive."
    )


def test_a_cmdlet_named_in_a_comment_is_not_a_cmdlet_that_is_called(tmp_path):
    """The measured surface is parsed, never grepped.

    A regular expression over the source counts every mention. The moment a
    comment explained why `Get-PnPTenantId` was NOT being called, the
    measurement said it was, and `docs/OBSERVABLE-SURFACE.md` published a
    collection path that did not exist.

    That document is the engine's own coverage question asked of itself, so a
    false positive there is the product overstating what it reads.

    MEASURED AGAINST A FILE WRITTEN FOR THIS, not against the real collector.
    The first version of this test asserted that one particular cmdlet stayed
    uncalled, and it broke within the hour when the collector started calling
    it: a test about a mechanism should not depend on today's inventory.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "surface", Path(__file__).resolve().parents[1] / "tools" / "surface.py"
    )
    surface = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(surface)

    (tmp_path / "sample.psm1").write_text(
        """
        function Test-Reading {
            # Get-PnPCommented is named here and never called.
            <#
                .DESCRIPTION
                Get-PnPInHelpBlock is named here and never called either.
            #>
            Get-PnPReallyCalled -Identity 'x'
        }
        """,
        encoding="utf-8",
    )

    called = surface.used(tmp_path)
    if not called:
        pytest.skip("pwsh is not installed, and the AST needs it")

    assert called == {"Get-PnPReallyCalled"}


def test_a_tenant_catalog_with_nothing_comparable_never_passes():
    """Zero out of nothing is not a finding.

    FOUND ON A REAL TENANT. The first app catalog this collector ever read
    positively was a tenant one: ten solutions, every `InstalledVersion` empty,
    because a tenant catalog records installation per site. The filter that
    counts solutions behind requires both version numbers, so it counted zero,
    and zero satisfied `greater-than 0` as false. SPO-SPFX-001 returned PASS --
    "every solution in this catalog is installed at the version the catalog
    holds" -- having compared nothing at all.

    That is the exact failure this engine exists to not commit, and it survived
    because the collector had only ever been observed against a site with no
    catalog. The count is now absent where nothing is comparable, and absent
    evidence is `unknown`.
    """
    import json

    from m365_governance import engine
    from m365_governance.loader import load_rule
    from m365_governance.resources import packaged

    evidence = json.loads(
        (
            packaged("fixtures")
            / "sharepoint"
            / "site-spfx-tenant-catalog-not-comparable.json"
        ).read_text(encoding="utf-8")
    )
    facts = evidence["facts"]["spfx"]
    assert facts["solution_count"]["value"] == 10, "the fixture stopped being the case"
    assert facts["comparable_count"]["value"] == 0
    assert facts["upgradable_count"]["state"] != "observed", (
        "a count of solutions behind was published for a catalog where no "
        "solution reports an installed version"
    )

    rule = load_rule(packaged("rules") / "sharepoint" / "SPO-SPFX-001.yaml").data
    result = engine._evaluate(rule, evidence)
    assert result.outcome.value == "unknown", (
        f"a tenant catalog with nothing comparable produced {result.outcome.value}"
    )
