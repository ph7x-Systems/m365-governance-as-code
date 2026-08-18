"""Producing a read from Graph, against recorded answers.

Nothing here reaches a tenant. The transport is injected, so every test states
exactly what Graph returned and the assertions are about what the producer made
of it — which is the only way to test a collector at all.

The interesting tests are the false positives: an application as the creator, a
folder that refuses halfway through, permissions in a different order, and a
digest that is absent rather than null.
"""

from __future__ import annotations

import json

import pytest

from conftest import SCHEMAS
from m365_governance import migration, migration_graph, registry
from m365_governance.graph import GraphReader

#: A token with no signature and a tenant claim. `Identity.from_token` reads the
#: claims; nothing here verifies a signature, and nothing should.
TOKEN = (
    "eyJhbGciOiJub25lIn0."
    + __import__("base64")
    .urlsafe_b64encode(
        json.dumps({"tid": "t", "aud": "https://graph.microsoft.com"}).encode()
    )
    .decode()
    .rstrip("=")
    + "."
)


@pytest.fixture(scope="module")
def schemas():
    return registry.SchemaRegistry.load(SCHEMAS)


def transport_for(answers: dict[str, dict]):
    """A transport that answers by path suffix, and refuses anything unstated.

    Unstated paths raise rather than returning an empty page: a collector that
    silently reads nothing from an address nobody wrote down is a collector
    whose test proves less than it appears to.
    """

    def transport(url: str, token: str):
        for suffix, body in answers.items():
            if url.endswith(suffix):
                if isinstance(body, int):
                    return body, json.dumps({"error": {"message": "no"}}), {}
                return 200, json.dumps(body), {}
        raise AssertionError(f"the producer asked for an address no test stated: {url}")

    return transport


def reader_for(answers: dict[str, dict]) -> GraphReader:
    return GraphReader(TOKEN, transport=transport_for(answers))


FILE = {
    "id": "1",
    "name": "plan.xlsx",
    "size": 4096,
    "file": {"hashes": {"quickXorHash": "AAAA"}},
    "createdBy": {"user": {"displayName": "a.pereira@example.test"}},
}


def test_one_listing_carries_three_dimensions():
    """Size, authorship and content, for the price of the enumeration."""
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="an estate",
    )
    assert document["items"] == {
        "/plan.xlsx": {
            "size": 4096,
            "author": "a.pereira@example.test",
            "content_digest": "AAAA",
        }
    }
    assert document["content_digest_algorithm"] == "quickXorHash"


def test_the_digest_algorithm_is_recorded_only_when_a_digest_was_found():
    """A digest without its algorithm is not comparable; an absent one needs no
    algorithm, and claiming one would describe a read that did not happen."""
    no_hash = {**FILE, "file": {"hashes": {}}}
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [no_hash]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert "content_digest_algorithm" not in document
    assert document["items"]["/plan.xlsx"]["content_digest"] is None


def test_an_application_creator_is_recorded_and_never_dropped():
    """`a migration tool created this` is the observation, not an absence."""
    by_tool = {
        **FILE,
        "createdBy": {"application": {"displayName": "a migration tool"}},
    }
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [by_tool]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert document["items"]["/plan.xlsx"]["author"] == "a migration tool"


def test_a_folder_that_refuses_becomes_coverage_not_an_empty_estate():
    document = migration_graph.read(
        reader_for(
            {
                "/root/children": {
                    "value": [FILE, {"id": "2", "name": "Archive", "folder": {}}]
                },
                "/items/2/children": 403,
            }
        ),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert list(document["items"]) == ["/plan.xlsx"], "what was read is kept"
    assert document["coverage"][0]["scope"] == "/Archive"
    assert document["coverage"][0]["state"] == "permission-denied"


def test_nothing_enumerated_at_all_is_refused_rather_than_returned_empty():
    """An estate nobody could read is not an estate with nothing in it."""
    with pytest.raises(migration_graph.Unreadable):
        migration_graph.read(
            reader_for({"/root/children": 403}),
            drive="d",
            read_id="r",
            taken_at="2026-03-01T09:00:00Z",
            estate="e",
        )


# -- the expensive two ------------------------------------------------------


def test_versions_and_permissions_are_not_fetched_unless_asked():
    """The transport refuses unstated addresses, so this asserts by not raising."""
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert "versions" not in document["items"]["/plan.xlsx"]
    assert "permissions" not in document["items"]["/plan.xlsx"]


def test_permissions_become_grants_and_links_from_one_read():
    document = migration_graph.read(
        reader_for(
            {
                "/root/children": {"value": [FILE]},
                "/items/1/permissions": {
                    "value": [
                        {
                            "roles": ["read"],
                            "link": {"scope": "anonymous", "type": "view"},
                        },
                        {
                            "roles": ["write"],
                            "grantedToV2": {"user": {"displayName": "Finance"}},
                        },
                    ]
                },
            }
        ),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
        with_permissions=True,
    )
    item = document["items"]["/plan.xlsx"]
    assert item["permissions"] == [["Finance", "write"]]
    assert item["sharing_links"] == ["anonymous:view"]


def test_grants_are_sorted_so_two_unchanged_reads_compare_equal():
    """The false positive this exists to prevent: same grants, other order."""
    order_a = {
        "value": [
            {"roles": ["full"], "grantedToV2": {"group": {"displayName": "Owners"}}},
            {"roles": ["edit"], "grantedToV2": {"group": {"displayName": "Members"}}},
        ]
    }
    order_b = {"value": list(reversed(order_a["value"]))}

    reads = [
        migration_graph.read(
            reader_for(
                {"/root/children": {"value": [FILE]}, "/items/1/permissions": order}
            ),
            drive="d",
            read_id="r",
            taken_at="2026-03-01T09:00:00Z",
            estate="e",
            with_permissions=True,
        )
        for order in (order_a, order_b)
    ]
    assert reads[0]["items"] == reads[1]["items"]

    findings = migration.compare(
        baseline=reads[0],
        verification=reads[1],
        dimensions=[{"name": "permissions", "state": "compared"}],
    )
    assert findings == [], "reordered grants are not a permission change"


def test_a_denied_permission_read_is_a_gap_on_that_item_not_a_missing_grant():
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE]}, "/items/1/permissions": 403}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
        with_permissions=True,
    )
    assert "permissions" not in document["items"]["/plan.xlsx"]
    assert document["coverage"][0]["scope"] == "/plan.xlsx"
    assert "permissions:" in document["coverage"][0]["detail"]


# -- end to end -------------------------------------------------------------


def test_two_graph_reads_produce_a_record_that_verifies(schemas):
    """The whole slice: enumerate twice, compare, and validate the record."""
    answers = {"/root/children": {"value": [FILE]}}
    moved = {
        **FILE,
        "createdBy": {"application": {"displayName": "a migration tool"}},
    }

    before = migration_graph.read(
        reader_for(answers),
        drive="d",
        read_id="before",
        taken_at="2026-03-01T09:00:00Z",
        estate="a library",
    )
    after = migration_graph.read(
        reader_for({"/root/children": {"value": [moved]}}),
        drive="d",
        read_id="after",
        taken_at="2026-03-09T09:00:00Z",
        estate="a library",
    )

    assert schemas.problems(before) == []
    assert schemas.problems(after) == []

    document = migration.record(
        baseline=before,
        verification=after,
        move={"kind": "tenant-to-tenant", "produced_by": "test"},
    )
    assert schemas.problems(document) == []
    assert migration.verify(document, schemas=schemas) == []

    compared = [d["name"] for d in document["dimensions"] if d["state"] == "compared"]
    assert compared == ["presence", "count", "content", "size", "authorship"], (
        "one listing bought three dimensions beyond presence and count"
    )

    outcomes = {(f["item"], f["dimension"]): f["outcome"] for f in document["findings"]}
    assert outcomes[("/plan.xlsx", "authorship")] == "fail"

    report = migration.report(document)
    assert "a migration tool" in report
    assert "%" not in report


def test_a_read_with_no_versions_says_who_decided(schemas):
    """Not fetched is the operator's choice, and reads differently from a gap."""
    before = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE]}}),
        drive="d",
        read_id="b",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    versions = next(
        d for d in migration.dimensions_for(before, before) if d["name"] == "versions"
    )
    assert versions["state"] == "not-compared"
    assert versions["limit"] == "not-carried", (
        "the surface can provide versions; this read did not fetch them, which "
        "is a different sentence from the surface being unable to"
    )


# -- what a real drive does that a fixture does not -------------------------


def test_a_folder_reached_twice_is_read_once_and_said_so():
    """A drive can carry a shortcut back to an ancestor."""
    loop = {
        "/root/children": {"value": [{"id": "2", "name": "A", "folder": {}}]},
        "/items/2/children": {
            "value": [FILE, {"id": "2", "name": "A-again", "folder": {}}]
        },
    }
    document = migration_graph.read(
        reader_for(loop),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert list(document["items"]) == ["/A/plan.xlsx"]
    assert any("already entered" in gap["detail"] for gap in document["coverage"])


def test_the_walk_stops_at_a_depth_and_reports_it_rather_than_crashing():
    """Deeper than the interpreter allows is a coverage gap, not a stack trace."""
    # Each level carries a new folder id so the cycle guard never fires, and a
    # file so the read is not empty for an unrelated reason.
    counter = {"n": 0}

    def transport(url: str, token: str):
        counter["n"] += 1
        return (
            200,
            json.dumps(
                {
                    "value": [
                        FILE,
                        {"id": f"lvl-{counter['n']}", "name": "deep", "folder": {}},
                    ]
                }
            ),
            {},
        )

    document = migration_graph.read(
        GraphReader(TOKEN, transport=transport),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert any("the walk stopped at" in gap["detail"] for gap in document["coverage"])
    assert counter["n"] <= migration_graph.MAX_DEPTH + 2


def test_an_item_shared_from_another_drive_is_listed_but_never_walked():
    """Its contents belong to an estate this read does not cover."""
    shared = {
        "id": "9",
        "name": "Shared",
        "folder": {},
        "remoteItem": {"id": "elsewhere"},
        "size": 12,
    }
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE, shared]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert "/Shared" in document["items"], "it is in the folder, so it is listed"
    gap = next(g for g in document["coverage"] if g["scope"] == "/Shared")
    assert gap["state"] == "not-supported"
    assert "another drive" in gap["detail"]


# -- what a client's estate does to a collector -----------------------------


def test_the_enumeration_follows_the_service_s_own_paging():
    """A page cap is the service's business; a collector that stopped at the
    first page would report a fraction of an estate as the whole of it."""
    pages = {
        "/root/children": {
            "value": [FILE],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/drives/d/root/children?page=2",
        },
        "children?page=2": {"value": [{**FILE, "id": "2", "name": "second.xlsx"}]},
    }
    document = migration_graph.read(
        reader_for(pages),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert sorted(document["items"]) == ["/plan.xlsx", "/second.xlsx"]


def test_a_throttled_read_is_retried_and_then_reported():
    """429 is the service asking for room, not the estate being empty."""
    attempts = {"n": 0}

    def transport(url: str, token: str):
        attempts["n"] += 1
        corpo = json.dumps({"error": {"message": "slow down"}})
        return 429, corpo, {"Retry-After": "0"}

    reader = GraphReader(TOKEN, transport=transport, sleep=lambda _: None)
    with pytest.raises(migration_graph.Unreadable):
        migration_graph.read(
            reader,
            drive="d",
            read_id="r",
            taken_at="2026-03-01T09:00:00Z",
            estate="e",
        )
    assert attempts["n"] > 1, "a single attempt is not a retry"


def test_an_item_deleted_during_the_read_is_a_gap_on_that_item():
    """Estates change while they are being read; that is not a finding."""
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE]}, "/items/1/permissions": 404}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
        with_permissions=True,
    )
    gap = next(g for g in document["coverage"] if g["scope"] == "/plan.xlsx")
    assert gap["state"] == "missing"
    assert "permissions" not in document["items"]["/plan.xlsx"]


def test_the_same_estate_read_twice_produces_identical_bytes():
    """A read that varied could not be compared against anything, including
    itself. Nothing here may come from the clock, a set's ordering, or a dict
    whose insertion order followed the service's."""
    from m365_governance import canonical

    shuffled = {
        "/root/children": {
            "value": [
                {**FILE, "id": "2", "name": "b.xlsx"},
                FILE,
                {"id": "3", "name": "Z", "folder": {}},
            ]
        },
        "/items/3/children": {"value": [{**FILE, "id": "4", "name": "deep.xlsx"}]},
    }
    reads = [
        migration_graph.read(
            reader_for(shuffled),
            drive="d",
            read_id="r",
            taken_at="2026-03-01T09:00:00Z",
            estate="e",
        )
        for _ in range(2)
    ]
    assert canonical.digest(reads[0]) == canonical.digest(reads[1])


def test_a_read_declares_the_identity_that_took_it():
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [FILE]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    assert document["read_by"]["kind"] == "not-established", (
        "this token carries neither roles nor scp, and that is a real answer "
        "about identity rather than a gap"
    )
    assert document["read_by"]["tenant"] == "t"
