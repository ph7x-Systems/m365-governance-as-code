"""Reading Microsoft Graph, read-only by construction.

Nothing here reaches a network. The transport is supplied, which is the whole
reason it is a parameter: a client that could only be tested against a live
tenant would be tested by nobody.

THE TWO THINGS THESE TESTS EXIST FOR, above all the rest:

1. **No mutation is reachable.** Not "is not currently reached" — not
   reachable. There is no argument to set and no branch to take.
2. **A denied read is never an empty tenant.** They arrive as the same absence
   in a naive client and they are opposite facts, and every rule written on
   this evidence depends on the difference surviving.
"""

from __future__ import annotations

import base64
import json

import pytest

from m365_governance.graph import (
    GLOBAL,
    RETRIES,
    GraphReader,
    Identity,
    Refused,
    Unavailable,
)

POLICIES = "identity/conditionalAccess/policies"


def _token(**claims) -> str:
    """A JWT-shaped string. Unsigned: nothing here verifies one."""
    body = {"tid": "11111111-2222-3333-4444-555555555555", **claims}
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def _answers(*replies):
    """A transport that returns these, in order, recording what it was asked."""
    calls: list[str] = []
    queue = list(replies)

    def transport(url, token):
        calls.append(url)
        status, body, headers = queue.pop(0) if queue else (500, "", {})
        return status, body, headers

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def _ok(items, next_link=None):
    document = {"value": items}
    if next_link:
        document["@odata.nextLink"] = next_link
    return (200, json.dumps(document), {})


def _reader(transport, token=None) -> GraphReader:
    return GraphReader(
        token or _token(scp="Policy.Read.All"),
        transport=transport,
        sleep=lambda _s: None,
    )


# ---------------------------------------------------------------------------
# no mutation is reachable
# ---------------------------------------------------------------------------


def test_no_mutating_verb_is_reachable_in_the_module():
    """Structural, not behavioural.

    A guard that could be turned off by passing an argument is a convention
    wearing the clothes of a constraint. This walks the syntax tree, so a verb
    named in a comment or a docstring explaining why it is absent does not
    count as present — the same distinction the collector surface measurement
    had to learn, and for the same reason: a check that greps flags the
    sentence that says the thing is not there.
    """
    import ast
    from pathlib import Path

    import m365_governance.graph as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    mutating = {"POST", "PUT", "PATCH", "DELETE"}

    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    # Docstrings are statements of intent rather than code, and a docstring is
    # the one string in a module that cannot become a request.
    docstrings = {
        ast.get_docstring(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef)
    }
    reachable = {s for s in literals - docstrings if s}

    offenders = sorted(s for s in reachable if s.upper() in mutating)
    assert not offenders, f"a mutating verb is reachable as a value: {offenders}"

    # And no name in the module can be one either: a verb held in a variable is
    # the way round a check on literals.
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert not {n for n in names if n.upper() in mutating}


def test_nothing_in_the_public_surface_accepts_a_method_or_a_body():
    """There is no argument to set. That is the point of checking signatures."""
    import inspect

    for name in ("read", "one"):
        parameters = set(inspect.signature(getattr(GraphReader, name)).parameters)
        assert not parameters & {"method", "verb", "data", "body", "json", "headers"}


# ---------------------------------------------------------------------------
# it never acquires authentication
# ---------------------------------------------------------------------------


def test_without_a_token_it_refuses_rather_than_acquiring_one():
    refused = pytest.raises(Refused, GraphReader, "")
    assert "never acquires one" in str(refused.value)


def test_the_identity_comes_from_the_token_and_the_token_never_travels():
    reader = _reader(_answers(_ok([])), token=_token(scp="Policy.Read.All User.Read"))

    assert reader.identity.kind == "delegated"
    assert reader.identity.scopes == ("Policy.Read.All", "User.Read")
    assert "token" not in {f for f in vars(reader.identity)}


def test_an_application_token_says_so_by_carrying_roles():
    reader = _reader(_answers(_ok([])), token=_token(roles=["Policy.Read.All"]))

    assert reader.identity.kind == "application"
    assert reader.identity.scopes == ("Policy.Read.All",)


def test_a_token_that_claims_neither_is_not_established():
    """A real answer about identity rather than a gap."""
    reader = _reader(_answers(_ok([])), token=_token())

    assert reader.identity.kind == "not-established"


def test_the_observed_directory_is_the_token_claim_and_nothing_else():
    """The only honest source for what a SESSION observed.

    Public discovery resolves which directory owns an address, which anybody
    can do without reaching the tenant. This is what the issuer says about the
    session that was actually opened, and the two must never share a field.
    """
    reader = _reader(_answers(_ok([])), token=_token(tid="abc", scp="Policy.Read.All"))

    assert reader.identity.observed_tenant_id == "abc"


# ---------------------------------------------------------------------------
# a denied read is never an empty tenant
# ---------------------------------------------------------------------------


def test_an_empty_collection_is_complete_and_says_the_tenant_has_none():
    read = _reader(_answers(_ok([]))).read(POLICIES)

    assert read.items == []
    assert read.complete
    assert read.unavailable is None


@pytest.mark.parametrize(
    "status,state,expected",
    [
        (401, "permission-denied", "says nothing about the tenant"),
        (403, "permission-denied", "Policy.Read.All"),
        (404, "not-supported", "not the same as a tenant having none"),
        (500, "missing", "answered 500"),
    ],
)
def test_every_refusal_is_carried_with_its_reason(status, state, expected):
    read = _reader(_answers((status, "", {}))).read(POLICIES)

    assert read.items == []
    assert not read.complete
    assert read.unavailable.state == state
    assert expected in read.unavailable.detail


def test_a_denied_read_and_an_empty_tenant_are_distinguishable():
    """The single most important property in this file.

    Both produce no items. One is a fact about permission and the other is a
    fact about the estate, and a rule over the first must answer `unknown`
    while a rule over the second may decide.
    """
    empty = _reader(_answers(_ok([]))).read(POLICIES)
    denied = _reader(_answers((403, "", {}))).read(POLICIES)

    assert empty.items == denied.items == []
    assert empty.complete and not denied.complete


def test_a_delegated_denial_names_the_directory_role_as_well_as_the_scope():
    """`Policy.Read.All` without a directory role is a documented failure mode.

    Recorded in the source audit, and named here so the reader is not sent to
    check a scope they already hold.
    """
    read = _reader(_answers((403, "", {}))).read(POLICIES)

    assert "Global Reader" in read.unavailable.detail
    assert "Conditional Access Administrator" in read.unavailable.detail


# ---------------------------------------------------------------------------
# pagination is the service's, not ours
# ---------------------------------------------------------------------------


def test_the_next_link_is_followed_and_never_constructed():
    nxt = f"{GLOBAL}/v1.0/{POLICIES}?$skiptoken=opaque"
    transport = _answers(_ok([{"id": "a"}], nxt), _ok([{"id": "b"}]))

    read = _reader(transport).read(POLICIES)

    assert [x["id"] for x in read.items] == ["a", "b"]
    assert read.complete
    # The second request used the service's URL verbatim.
    assert transport.calls[1] == nxt


def test_a_refusal_on_a_later_page_keeps_what_was_already_read():
    """A partial read of a tenant is worth exactly what it read."""
    nxt = f"{GLOBAL}/v1.0/{POLICIES}?$skiptoken=opaque"
    read = _reader(_answers(_ok([{"id": "a"}], nxt), (403, "", {}))).read(POLICIES)

    assert [x["id"] for x in read.items] == ["a"]
    assert not read.complete
    assert read.unavailable.state == "permission-denied"


def test_a_next_link_that_repeats_a_page_is_stopped_rather_than_followed():
    same = f"{GLOBAL}/v1.0/{POLICIES}"
    read = _reader(_answers(_ok([{"id": "a"}], same))).read(POLICIES)

    assert not read.complete
    assert "repeated a page already read" in read.unavailable.detail


# ---------------------------------------------------------------------------
# throttling is bounded, and exhaustion is partial rather than empty
# ---------------------------------------------------------------------------


def test_a_throttled_request_is_retried_and_then_succeeds():
    transport = _answers((429, "", {"Retry-After": "1"}), _ok([{"id": "a"}]))

    read = _reader(transport).read(POLICIES)

    assert read.complete and len(read.items) == 1
    assert len(transport.calls) == 2


def test_the_retry_budget_is_bounded_and_exhaustion_is_reported():
    """A collector that retried until it succeeded would turn a tenant that is
    refusing us into a process that never ends."""
    throttled = [(429, "", {"Retry-After": "1"})] * (RETRIES + 1)
    transport = _answers(*throttled)

    read = _reader(transport).read(POLICIES)

    assert not read.complete
    assert read.unavailable.state == "partial"
    assert len(transport.calls) == RETRIES + 1


def test_an_unreadable_retry_after_does_not_stop_the_read():
    transport = _answers((429, "", {"Retry-After": "soon"}), _ok([]))

    assert _reader(transport).read(POLICIES).complete


# ---------------------------------------------------------------------------
# a shape this engine does not understand is not an empty tenant either
# ---------------------------------------------------------------------------


def test_two_hundred_without_a_value_collection_is_refused():
    read = _reader(_answers((200, json.dumps({"id": "x"}), {}))).read(POLICIES)

    assert not read.complete
    assert read.unavailable.state == "invalid"
    assert "cannot tell an empty tenant" in read.unavailable.detail


def test_two_hundred_that_is_not_json_is_refused():
    read = _reader(_answers((200, "<html>sign in</html>", {}))).read(POLICIES)

    assert not read.complete
    assert read.unavailable.state == "invalid"


def test_a_single_resource_is_read_as_one_item_rather_than_a_collection():
    """Security Defaults is one object. Wrapping it keeps one shape downstream."""
    document = {"id": "default", "isEnabled": True}
    read = _reader(_answers((200, json.dumps(document), {}))).one(
        "policies/identitySecurityDefaultsEnforcementPolicy"
    )

    assert read.complete
    assert read.items == [document]


# ---------------------------------------------------------------------------
# the endpoint is configuration, because four clouds do not share an address
# ---------------------------------------------------------------------------


def test_the_cloud_endpoint_is_configuration_and_not_a_constant():
    transport = _answers(_ok([]))
    reader = GraphReader(
        _token(scp="Policy.Read.All"),
        endpoint="https://microsoftgraph.chinacloudapi.cn",
        transport=transport,
        sleep=lambda _s: None,
    )

    reader.read(POLICIES)

    assert transport.calls[0].startswith(
        "https://microsoftgraph.chinacloudapi.cn/v1.0/"
    )


def test_the_source_api_records_the_version_that_was_read():
    assert _reader(_answers(_ok([]))).source_api == "Microsoft Graph v1.0"


# ---------------------------------------------------------------------------
# one area failing never removes another's result
# ---------------------------------------------------------------------------


def test_areas_are_read_independently():
    from m365_governance.graph import iter_reads

    transport = _answers(_ok([{"id": "a"}]), (403, "", {}))
    reader = _reader(transport)

    outcomes = dict(
        iter_reads(reader, {"policies": POLICIES, "locations": "x/namedLocations"})
    )

    assert outcomes["policies"].complete
    assert not outcomes["locations"].complete
    assert outcomes["policies"].items == [{"id": "a"}]


def test_the_absent_state_vocabulary_is_the_evidence_contracts_own():
    """One vocabulary across the product, rather than a second one for Graph."""
    allowed = {"missing", "not-supported", "permission-denied", "partial", "invalid"}

    for status in (401, 403, 404, 429, 500):
        assert Unavailable.of(status, "x").state in allowed


def test_an_identity_carries_no_credential_field():
    fields = {f.lower() for f in vars(Identity("delegated", "t", ()))}

    assert not fields & {"token", "secret", "password", "certificate", "assertion"}
