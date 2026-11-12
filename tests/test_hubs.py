"""The hub enumeration: one collector, one command, and what it may publish."""

import json

from m365_governance import collecting, grouping, presenting

FIXTURES = collecting.COLLECTOR.parents[3] / "fixtures" / "sharepoint"
MODULE = collecting.COLLECTOR.parent / "modules" / "Hubs.psm1"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_the_grouped_command_is_the_collection_and_nothing_else():
    assert grouping.regroup(["spo", "hub", "list", "--output", "csv"]) == [
        "collect",
        "hubs",
        "--output",
        "csv",
    ]


def test_the_slice_reads_one_cmdlet_and_feeds_no_rule_by_decision():
    hubs = collecting.SLICES["hubs"]
    assert hubs.reads == ("Get-PnPHubSite",)
    assert hubs.produces_findings is False
    assert "operator" in hubs.consumed_by
    assert hubs.needs_tenant and not hubs.needs_site and hubs.writes_many


def test_a_tenant_with_no_hub_still_has_a_document_to_say_so():
    """Zero is an observation. The count lives on the tenant document, which is
    written whether or not any hub follows it."""
    script = collecting.COLLECTOR.read_text(encoding="utf-8")
    mode = script.split("'HubSites' {", 1)[1]
    assert mode.index("Get-HubPopulationFacts") < mode.index("foreach ($hub in $hubs)")
    tenant = _fixture("tenant-hubs-two-registered")
    assert tenant["resource"]["type"] == "tenant"
    assert tenant["facts"]["hubs"]["count"]["state"] == "observed"


def test_who_may_associate_is_a_count_and_never_a_name():
    """The principals are people and groups. The fact is how many."""
    code = "\n".join(
        line
        for line in MODULE.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )
    assert "$principals.Count" in code
    for leak in ("PrincipalName", "DisplayName", "LoginName", "Email"):
        assert leak not in code
    hub = _fixture("site-hub-association-restricted")["facts"]["hub"]
    assert isinstance(hub["association_principals"]["value"], int)


def test_the_view_shows_a_hub_as_a_row_with_its_facts():
    headers, rows = presenting.table([_fixture("site-hub-association-restricted")])
    row = dict(zip(headers, rows[0], strict=True))
    assert row["name"] == "Intranet"
    assert row["hub.requires_join_approval"] == "true"
    assert row["hub.association_restricted"] == "true"
    assert row["hub.association_principals"] == "2"
    assert "{" not in "".join(rows[0]), "a family was printed as its own keys"
