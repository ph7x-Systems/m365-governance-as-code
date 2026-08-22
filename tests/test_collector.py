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

import json
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


def test_a_slice_runs_the_collector_it_names_with_the_parameters_it_takes():
    """Routing, proven without a tenant.

    `Slice.source` said which KIND of collector answers a slice and `run_slice`
    read it as which ONE, because for as long as there was a single PowerShell
    entry point the two questions had the same answer. Licensing is the second:
    a different script, `-TenantHost` rather than `-TenantUrl`, a `-Period` no
    other slice takes, and no `-CertificatePath` at all. Routed by `source`
    alone it would have sent a mode `Get-SpoEvidence.ps1` has never heard of,
    and the first thing anybody would have seen is a parameter-binding error
    four seconds into a run against a real directory.
    """
    from m365_governance import collecting

    argv = collecting.run_slice(
        "licensing",
        client_id="00000000-0000-0000-0000-000000000000",
        output=Path("/nowhere"),
        tenant_url="contoso.onmicrosoft.com",
        period="D30",
        certificate_path=Path("/nowhere/cert.pfx"),
        dry_run=True,
    ).stdout.split()

    assert argv[argv.index("-File") + 1].endswith("licensing/Get-LicensingEvidence.ps1")
    assert argv[argv.index("-Mode") + 1] == "Licensing"
    assert argv[argv.index("-TenantHost") + 1] == "contoso.onmicrosoft.com"
    assert argv[argv.index("-Period") + 1] == "D30"
    assert "-TenantUrl" not in argv
    assert "-SiteUrl" not in argv
    # The collector takes a thumbprint from the machine store and has never
    # been run app-only. A path it cannot bind is worse than no path.
    assert "-CertificatePath" not in argv

    spo = collecting.run_slice(
        "sites",
        client_id="00000000-0000-0000-0000-000000000000",
        output=Path("/nowhere"),
        tenant_url="https://contoso-admin.sharepoint.com",
        dry_run=True,
    ).stdout.split()
    assert spo[spo.index("-File") + 1].endswith("sharepoint/Get-SpoEvidence.ps1")
    assert "-TenantUrl" in spo and "-Period" not in spo


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

    # THIS COLLECTOR'S slices only. A Graph slice has no `-SiteUrl` to pass
    # and no PnP session to open, and neither has a PowerShell collector of its
    # own: `Connection.psm1` is `Get-SpoEvidence.ps1`'s, and requiring the
    # licensing modes to appear in its admin list would be asking one collector
    # to declare another's work.
    mine = collecting.SLICES["sites"].script
    siteless = {
        s.mode
        for s in collecting.SLICES.values()
        if not s.needs_site and s.source == "powershell" and s.script == mine
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


def test_no_evidence_family_disappears_from_the_bundle():
    """A family that exists here and not in the bundle is invisible downstream.

    `publish-contracts.py` globbed `fixtures/sharepoint` alone, written when
    that was the only family there was. Two arrived afterwards. `licensing`
    was caught by hand; `entra` had been absent for longer, with four fixtures
    a consumer never received, and the bundle looked healthy the whole time
    because seventy-one SharePoint samples were in it.

    THE LIST IS NOT THE PROBLEM. A named list is the right shape: it makes
    adding a family deliberate. What was missing is anything holding the list
    to the tree, so this compares the two and requires an exclusion to be
    written down rather than left to be noticed.
    """
    import json
    import re

    publisher = DATA.parents[2] / "tools" / "publish-contracts.py"
    published = re.search(
        r"families = \(([^)]*)\)", publisher.read_text(encoding="utf-8")
    )
    assert published, "the publisher no longer names its families"
    named = set(re.findall(r'"([a-z0-9-]+)"', published.group(1)))

    #: Families of documents that are not evidence and produce no run. They are
    #: carried into the bundle by their own steps, and each one is here because
    #: somebody decided it, not because a glob skipped it.
    not_evidence = {
        "archive": "documents of superseded contract versions",
        "assessment": "assessments, copied by their own publish step",
        "comparison": "comparisons, copied by their own publish step",
        "migration": "lists of documents rather than evidence; `evaluate` refuses them",
    }

    root = DATA / "fixtures"
    families = {}
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(child.glob("*.json")):
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict) and "facts" in doc and "resource" in doc:
                families[child.name] = f.name
                break

    missing = sorted(set(families) - named - set(not_evidence))
    assert not missing, (
        "evidence families in this repository that no consumer receives: "
        + ", ".join(f"{m} (e.g. {families[m]})" for m in missing)
        + ".\n  Add them to `families` in tools/publish-contracts.py, or record "
        "why they are excluded in `not_evidence` above."
    )


def test_every_packaged_fixture_can_be_read_by_the_tool_that_reads_evidence():
    """A document this engine produced, opened by this engine.

    THE FIRST LIVE LICENSING RUN PRODUCED A DOCUMENT `stats` COULD NOT OPEN.
    The collection had succeeded -- a tenant was read, the usage report was
    returned -- and `coverage.unavailable` carried a `null` for an area that
    had completed, so the reader raised on a member of `None`. Every test
    passed, because no test had ever asked a reader to open the fixtures.

    It reads every fixture rather than a chosen one: the defect was in a branch
    nobody had a fixture for, and the only defence against that is breadth.
    """
    from m365_governance import inspect as inspect_module

    fixtures = sorted((DATA / "fixtures").glob("*/*.json"))
    assert fixtures, "no fixtures found"

    unreadable = []
    for path in fixtures:
        document = json.loads(path.read_text(encoding="utf-8"))
        if "facts" not in document or "coverage" not in document:
            # Assessments and comparisons are not evidence and `stats` does not
            # claim to read them.
            continue
        try:
            inspect_module.stats(path)
        except Exception as raised:  # noqa: BLE001 - the point is that none does
            unreadable.append(f"{path.name}: {type(raised).__name__}: {raised}")

    assert not unreadable, "evidence this engine cannot read:\n  " + "\n  ".join(
        unreadable
    )


def test_a_coverage_area_that_completed_is_not_also_reported_as_unavailable():
    """`unavailable` holds areas with a reason, and nothing else.

    The collector built the table with one branch per area and assigned `$null`
    to the ones that completed. PowerShell keeps the key, `ConvertTo-Json`
    writes `"usage": null`, and the document says an area both completed and
    did not.
    """
    for path in sorted((DATA / "fixtures").glob("*/*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        coverage = document.get("coverage")
        # The migration contracts carry a `coverage` of their own shape, a list
        # rather than the evidence envelope's map. This is about the evidence
        # contract and says nothing about theirs.
        if not isinstance(coverage, dict):
            continue
        unavailable = coverage.get("unavailable") or {}
        for area, reason in unavailable.items():
            assert isinstance(reason, dict) and reason.get("state"), (
                f"{path.name}: coverage.unavailable[{area!r}] carries no reason. "
                "An area is unavailable with a state and a detail, or it is not "
                "in this table."
            )
            assert area not in coverage.get("completed", []), (
                f"{path.name}: {area!r} is both completed and unavailable."
            )


#: Facts whose published contract is an array. PowerShell unwraps a one-element
#: pipeline result, so each of these can change JSON TYPE with the number of
#: things it found unless the producer forces the shape after the whole
#: pipeline.
ARRAY_FACTS = ("usage_window_days", "usage_report_refresh_date", "skus")


@pytest.mark.skipif(not shutil.which("pwsh"), reason="PowerShell 7 is not installed")
def test_an_array_fact_is_an_array_at_zero_one_and_many():
    """The bug this exists for changed a contract's TYPE with its cardinality.

    `usage_window_days` was built by a pipeline whose input was wrapped and
    whose result was not, so it published `7` for one period and `[7, 30]` for
    two. A consumer parsing it as a number breaks on the second period; one
    parsing it as a list breaks on the first. Nothing caught it: the fixture
    had the array and no test had ever compared the fixture against what the
    collector actually emits.

    THE ASSERTION IS ABOUT JSON TYPE, NOT CONTENT. Content was never wrong.
    """
    module = COLLECTORS / "powershell" / "licensing" / "modules" / "Licensing.psm1"
    shared = COLLECTORS / "powershell" / "sharepoint" / "modules" / "Evidence.psm1"
    script = f"""
        Import-Module '{shared}' -Force
        Import-Module '{module}' -Force
        $out = [ordered]@{{}}
        foreach ($n in 0, 1, 3) {{
            $windows = @(0..($n - 1) | ForEach-Object {{
                [pscustomobject]@{{
                    report = "svc$_"; window_days = (7 * ($_ + 1))
                    report_refresh_date = "2026-08-0$($_ + 1)"
                    rows = 1; rows_naming_a_principal = 0
                }}
            }})
            if ($n -eq 0) {{ $windows = $null }}
            $facts = Get-LicensingFacts -SubscribedSkus @() -Assignments @() `
                -ReportSettings $null -UsageWindows $windows -Attempts $null
            $out["$n"] = $facts.licensing
        }}
        $out | ConvertTo-Json -Depth 12
    """
    done = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    produced = json.loads(done.stdout)

    wrong = []
    for cardinality, facts in produced.items():
        for name in ARRAY_FACTS:
            node = facts.get(name)
            if node is None or node.get("state") != "observed":
                # An absent fact is a different statement and has its own state.
                continue
            if not isinstance(node.get("value"), list):
                wrong.append(
                    f"{name} at {cardinality} item(s) is "
                    f"{type(node['value']).__name__}, not a list"
                )

    assert not wrong, (
        "a published array changed shape with how much it found:\n  "
        + "\n  ".join(wrong)
    )
