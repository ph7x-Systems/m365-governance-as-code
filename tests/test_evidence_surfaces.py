"""The surfaces a claim may rest on, and the fact that they are not one list.

`I searched` is not a method. This holds the registry to the three properties
that make it worth having: every surface says what it settles AND what it does
not, every one names where to look, and the two surfaces that may never be a
basis are marked as such.
"""

from __future__ import annotations

import json

import pytest

from conftest import DATA

REGISTRY = DATA / "evidence-surfaces.json"


@pytest.fixture(scope="module")
def surfaces():
    with REGISTRY.open(encoding="utf-8") as handle:
        return json.load(handle)["surfaces"]


def test_every_surface_says_what_it_does_not_settle(surfaces):
    """A source that only says what it proves teaches a reader to over-read it."""
    for surface in surfaces:
        assert surface["settles"], surface["id"]
        assert surface["does_not_settle"], surface["id"]
        assert surface["where"], f"{surface['id']} names no place to look"


def test_the_response_outranks_the_prose(surfaces):
    """Where a reference page and a tenant's own answer disagree, the answer is
    what is true and the page is what somebody intended."""
    rank = {s["id"]: s["rank"] for s in surfaces}

    assert rank["tenant-response"] < rank["reference"]
    assert rank["reference"] < rank["roadmap"]


def test_a_portal_is_never_a_basis(surfaces):
    """THE POINT OF THE WHOLE PRODUCT. A portal settles what an administrator is
    SHOWN, which is what they believe, and not what is true. It is read as the
    second surface so a divergence can be recorded as evidence, and a rule that
    rested on it would be citing the thing being audited."""
    portal = next(s for s in surfaces if s["id"] == "admin-portal")

    assert "Never a basis for a rule" in portal["note"]
    assert "SECOND SURFACE" in portal["note"]
    assert "what is true" in portal["does_not_settle"]


def test_community_documentation_settles_nothing(surfaces):
    """It is where to look next, not what to cite."""
    community = next(s for s in surfaces if s["id"] == "community")

    assert community["settles"] == "nothing on its own"
    assert community["rank"] == max(s["rank"] for s in surfaces)


def test_the_change_surfaces_are_present_and_distinct(surfaces):
    """Reference pages say what the product does. They do not say what it is
    about to stop doing, and a rule correct on the day it was written keeps
    being published long after it stopped being."""
    ids = {s["id"] for s in surfaces}

    assert {"message-center", "roadmap", "graph-changelog", "retirement"} <= ids

    roadmap = next(s for s in surfaces if s["id"] == "roadmap")
    assert "never a fact" in roadmap["settles"]


def test_a_rule_that_cites_a_place_cites_one_of_these(surfaces):
    """Every source URL on every shipped rule belongs to a named surface. A
    citation outside this list is a claim resting on something nobody agreed
    was evidence."""
    import yaml

    known = [place.split()[0] for surface in surfaces for place in surface["where"]]
    hosts = {place.split("/")[2] for place in known if place.startswith("http")}

    for path in sorted((DATA / "rules").rglob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            rule = yaml.safe_load(handle)

        for source in rule.get("basis", {}).get("sources", []):
            host = source["url"].split("/")[2]
            assert host in hosts, (
                f"{path.stem} cites {host}, which is not a named evidence "
                f"surface. Add the surface deliberately or cite one that exists."
            )
