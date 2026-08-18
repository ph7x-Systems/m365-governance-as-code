"""Producing a read from Graph, against recorded answers.

Nothing here reaches a tenant. The transport is injected, so every test states
exactly what Graph returned and the assertions are about what the producer made
of it — which is the only way to test a collector at all.

The interesting tests are the false positives: an application as the creator, a
folder that refuses halfway through, permissions in a different order, and a
digest that is absent rather than null.
"""

from __future__ import annotations

import io
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
        body = json.dumps({"error": {"message": "slow down"}})
        return 429, body, {"Retry-After": "0"}

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


# ── the transport itself ─────────────────────────────────────────────────────
#
# Every test above injects a fake transport, which is what makes them tests of
# the producer rather than of the network. The consequence is that `_https` —
# the one place a request actually leaves this process — was never exercised at
# all, and it is the function that decides what a refusal from Graph looks like
# to everything upstream.
#
# These do not reach a tenant either. They replace `urlopen` and assert the
# three shapes the rest of the reader is written against.


class _Answer:
    """What `urlopen` yields: a context manager with a status, a body and
    headers."""

    def __init__(self, status: int, body: bytes, headers: dict[str, str]):
        self.status = status
        self._body = body
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self._body


def test_a_good_answer_returns_status_body_and_headers(monkeypatch):
    from m365_governance import graph

    def urlopen(request, timeout=None):
        # The structural half of read-only: the method is a literal and there
        # is no parameter for it. If somebody adds one, this fails here.
        assert request.get_method() == "GET"
        assert request.headers["Authorization"].startswith("Bearer ")
        return _Answer(200, b'{"value": []}', {"Content-Type": "application/json"})

    monkeypatch.setattr(graph.urllib.request, "urlopen", urlopen)
    status, body, headers = graph._https("https://graph.microsoft.com/v1.0/me", "t")
    assert status == 200
    assert json.loads(body) == {"value": []}
    assert headers["Content-Type"] == "application/json"


def test_a_refusal_from_graph_is_returned_rather_than_raised(monkeypatch):
    """403 and 429 are answers, not breakages: the caller decides what to do
    with them, and the 429 carries the `Retry-After` the reader honours."""
    from m365_governance import graph

    def urlopen(request, timeout=None):
        raise graph.urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {"Retry-After": "3"},
            io.BytesIO(b'{"error": {"message": "slow down"}}'),
        )

    monkeypatch.setattr(graph.urllib.request, "urlopen", urlopen)
    status, body, headers = graph._https("https://graph.microsoft.com/v1.0/me", "t")
    assert status == 429
    assert "slow down" in body
    assert headers["Retry-After"] == "3"


def test_an_unreachable_graph_is_a_refusal_carrying_the_reason(monkeypatch):
    """With no network there is no answer to interpret at all, which is a
    different thing from an answer that says no. The reason travels, because a
    `Refused` without one leaves the reader guessing between DNS, TLS and a
    proxy."""
    from m365_governance import graph

    def urlopen(request, timeout=None):
        raise graph.urllib.error.URLError("name or service not known")

    monkeypatch.setattr(graph.urllib.request, "urlopen", urlopen)
    with pytest.raises(graph.Refused) as refusal:
        graph._https("https://graph.microsoft.com/v1.0/me", "t")
    assert "name or service not known" in str(refusal.value)


# ── what a real estate holds, as synthetic shapes ────────────────────────────
#
# Two classes were observed on a real tenant on 2026-08-18 and are recorded in
# NEXT-SLICE.md. Neither is copied here: the shapes are rebuilt, the data is
# invented, and no identifier, path or name from that tenant appears.


PRE_PLATFORM = {
    "id": "old",
    "name": "index.js",
    "size": 512,
    # 1984, decades before the service existed. A package manager writes a
    # deterministic timestamp and the upload preserves it, so a real drive
    # carries dates that predate the thing storing them.
    "createdDateTime": "1984-06-22T21:50:00Z",
    "lastModifiedDateTime": "1984-06-22T21:50:00Z",
    "file": {"hashes": {"quickXorHash": "BBBB"}},
    "createdBy": {"user": {"displayName": "a.pereira@example.test"}},
}


def test_a_timestamp_older_than_the_platform_changes_nothing_in_the_read():
    """AGE IS NOT A VERDICT, and this test exists so it never becomes one.

    A date from 1984 is semantically absurd and legitimately survives
    transport. The read carries what it observed and infers nothing from how
    old it is: no coverage gap, no flag, no absence. If somebody later teaches
    the producer that an old timestamp means corruption, this goes red, which
    is the point.
    """
    document = migration_graph.read(
        reader_for({"/root/children": {"value": [PRE_PLATFORM]}}),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    item = document["items"]["/index.js"]
    assert item == {
        "size": 512,
        "author": "a.pereira@example.test",
        "content_digest": "BBBB",
    }
    assert document["coverage"] == []


def test_two_reads_of_the_same_ancient_item_compare_as_unchanged(schemas):
    """The pair that matters: an item nobody has touched since 1984 must
    compare equal to itself across a move. An age heuristic anywhere in the
    chain would turn the most stable file in an estate into a finding."""

    def side():
        return migration_graph.read(
            reader_for({"/root/children": {"value": [PRE_PLATFORM]}}),
            drive="d",
            read_id="r",
            taken_at="2026-03-01T09:00:00Z",
            estate="e",
        )

    before = side()
    after = dict(side(), read_id="r2", taken_at="2026-03-08T09:00:00Z")
    record = migration.record(
        baseline=before,
        verification=after,
        move={"kind": "tenant-to-tenant", "produced_by": "m365-governance 0.1.0"},
    )
    assert migration.verify(record, schemas=schemas) == []
    assert [f for f in record["findings"] if f["outcome"] == "fail"] == []


def deep_answers(levels: int) -> dict[str, dict]:
    """A drive nested `levels` deep, each folder holding the next and the last
    holding one file. Rebuilt from the shape a real drive showed: seventeen
    segments with a dependency directory inside another one."""
    answers: dict[str, dict] = {}
    answers["/root/children"] = {"value": [{"id": "f0", "name": "d0", "folder": {}}]}
    for n in range(levels - 1):
        answers[f"/items/f{n}/children"] = {
            "value": [{"id": f"f{n + 1}", "name": f"d{n + 1}", "folder": {}}]
        }
    answers[f"/items/f{levels - 1}/children"] = {"value": [FILE]}
    return answers


def test_a_deeply_nested_drive_is_walked_to_the_leaf():
    """Seventeen levels is what a real drive showed, and it is well inside the
    guard. The margin is measured now rather than assumed: the item at the
    bottom arrives with its whole path as its identity."""
    document = migration_graph.read(
        reader_for(deep_answers(17)),
        drive="d",
        read_id="r",
        taken_at="2026-03-01T09:00:00Z",
        estate="e",
    )
    expected = "/" + "/".join(f"d{n}" for n in range(17)) + "/plan.xlsx"
    assert list(document["items"]) == [expected]
    assert document["coverage"] == []
    assert expected.count("/") == 18


def flat_answers(items: int, per_folder: int = 200) -> dict[str, dict]:
    """A synthetic estate of `items` files in folders of `per_folder`."""
    folders = (items + per_folder - 1) // per_folder
    answers: dict[str, dict] = {
        "/root/children": {
            "value": [
                {"id": f"F{i}", "name": f"dir{i}", "folder": {}} for i in range(folders)
            ]
        }
    }
    for i in range(folders):
        answers[f"/items/F{i}/children"] = {
            "value": [
                {
                    "id": f"{i}-{j}",
                    "name": f"f{j}.dat",
                    "size": 1024,
                    "file": {"hashes": {"quickXorHash": "AAAA"}},
                    "createdBy": {"user": {"displayName": "a.pereira@example.test"}},
                }
                for j in range(per_folder)
            ]
        }
    return answers


def test_the_producer_holds_a_large_estate_at_a_measured_cost():
    """THE WHOLE ESTATE IS MATERIALISED, and this says what that costs.

    The walk keeps every item and every entered folder id in memory, which is
    a deliberate trade: an estate held whole can be canonicalised, digested
    and compared without a second pass. The question was never whether it
    holds; it is what it costs at the scale a real drive reaches, and a real
    tenant showed hundreds of thousands of items is an ordinary number.

    Measured on this machine: 250,000 items read in about four seconds at a
    100 MB peak, and a verification of two such reads at 142 MB. Roughly 410
    bytes an item, linear. This test runs a twentieth of that so it stays in
    a suite, and bounds the per-item cost with headroom rather than pinning a
    number that would go red on a different interpreter.
    """
    import tracemalloc

    items = 12_000
    tracemalloc.start()
    try:
        document = migration_graph.read(
            reader_for(flat_answers(items)),
            drive="d",
            read_id="r",
            taken_at="2026-03-01T09:00:00Z",
            estate="e",
        )
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    assert len(document["items"]) == items
    per_item = peak / items
    assert per_item < 2048, (
        f"the read costs {per_item:.0f} bytes an item, and it has cost around "
        "410. Something now keeps more of each entry than the read carries, "
        "and at a quarter of a million items that is the difference between "
        "100 MB and a machine that stops."
    )
