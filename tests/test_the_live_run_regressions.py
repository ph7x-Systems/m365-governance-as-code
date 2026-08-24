"""Seven faults a real directory found on 2026-08-24, pinned so they stay found.

NONE OF THESE WAS VISIBLE OFFLINE, and that is the point of the file rather
than an excuse for it. The suite was green at 1508 tests while the command line
could not authenticate to Microsoft Graph, could not read a filtered
collection, refused its own output, and skipped the directory entirely. Every
one of them is a boundary the tests mocked: a subprocess that was never spawned,
a request that was never sent, a directory that was never walked with a real
run's files in it.

So these are written against the SEAM rather than against the network. A test
here must fail if somebody reintroduces the fault, and must not require a
tenant to say so -- otherwise it is a test nobody runs and the fault comes back
between two of the runs that would have caught it.

The three the owner named as the ones that must never regress:

    run must collect Entra when collect does
    Graph token arguments must bind
    a proof draft must never be mistaken for evidence
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from m365_governance import (  # noqa: E402
    collecting,
    connecting,
    graph,
    graph_token,
    running,
)


# ── 1. run must collect the directory whenever collect could ────────────────


class _Args:
    """Only what the planner and the application reader look at."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


APPLICATION = dict(
    client_id="00000000-0000-4000-8000-000000000001",
    tenant_id="00000000-0000-4000-8000-000000000002",
    certificate_path="/nowhere/app.pfx",
    tenant_url="https://contoso-admin.sharepoint.com",
    certificate_password_env="PH7X_CERT_PASSWORD",
)


def test_run_plans_the_graph_slices_when_it_holds_what_collect_would_use():
    """`collect` mints a token from the certificate; `run` must not refuse to.

    The planner asked only whether a token was already exported, so with a
    complete application registration on the command line `run` marked every
    Graph slice `no token` and collected none of them. The operator had
    supplied everything needed. What they got was a report with no directory in
    it and a plan that said `no token`, which is true and reads as though
    nothing could be done about it.
    """
    from m365_governance import cli

    args = _Args(**APPLICATION)
    assert cli._application_from(args).complete

    steps = running.plan(
        site_url="",
        tenant_url=APPLICATION["tenant_url"],
        has_graph_token=cli._application_from(args).complete,
        has_powershell=True,
    )
    graph_steps = [s for s in steps if s.slice.source == "graph"]
    assert graph_steps, "there are no Graph slices to plan"
    assert all(s.planned is running.Planned.ATTEMPT for s in graph_steps), (
        "a Graph slice was skipped while the run held the credentials that "
        "would have collected it"
    )


def test_run_would_not_hand_a_graph_slice_to_the_powershell_path():
    """The other half of the same omission, and it hid behind the first.

    Planning the slices is not enough: `run_slice` is the PowerShell path and
    refuses anything else, so a Graph slice reaching execution would have been
    refused too. Neither half was ever observed, because the planner never let
    one get that far.
    """
    with pytest.raises(Exception) as refusal:
        collecting.run_slice(
            "tenant-governance",
            client_id="",
            output=Path("/nowhere"),
            site_url="",
            tenant_url=APPLICATION["tenant_url"],
            device_login=False,
        )
    assert "graph" in str(refusal.value).lower(), (
        "the PowerShell path no longer says why it cannot run a Graph slice, "
        "which is what tells the caller to dispatch it elsewhere"
    )

    from m365_governance import cli

    assert "tenant-governance" in cli.GRAPH_SLICES, (
        "the dispatch table `run` uses for Graph slices no longer carries it"
    )


# ── 2. the token's arguments must actually bind ─────────────────────────────


def test_the_token_script_reads_its_inputs_from_the_environment():
    """`pwsh -Command <text> -ClientId x` does not bind `-ClientId`.

    The script declared a `param()` block and was invoked that way, so every
    value arrived null and PnP reported the first null it refuses: `Cannot bind
    argument to parameter 'Tenant'`. A message about the directory, produced by
    a working certificate against a working directory, and no Graph slice could
    collect from any tenant.
    """
    script = graph_token.SCRIPT
    # A LINE THAT DECLARES ONE, not the letters appearing in a comment about
    # why there is none. The looser check failed on this module's own
    # explanation of the fault, which is the same shape as the fault.
    declares = [
        line for line in script.splitlines() if line.strip().startswith("param(")
    ]
    assert not declares, (
        "the token script takes named parameters again. With `-Command` they "
        f"are not bound, and this module may never write a file: {declares}"
    )
    for variable in (
        "PH7X_GRAPH_CLIENT_ID",
        "PH7X_GRAPH_TENANT_ID",
        "PH7X_GRAPH_CERTIFICATE",
        "PH7X_GRAPH_URL",
        "PH7X_GRAPH_PASSWORD_ENV",
    ):
        assert f"$env:{variable}" in script, f"{variable} is not read by the script"


def test_every_value_the_script_reads_is_one_the_caller_supplies():
    """The two lists are the same list, or a value silently arrives empty.

    This is the shape of the original fault rather than its letter: the caller
    passed five things and the child received none of them, and nothing
    compared the two ends.
    """
    application = graph_token.Application(**APPLICATION)
    supplied = graph_token.environment_for(application)

    assert set(supplied) == {
        "PH7X_GRAPH_CLIENT_ID",
        "PH7X_GRAPH_TENANT_ID",
        "PH7X_GRAPH_CERTIFICATE",
        "PH7X_GRAPH_URL",
        "PH7X_GRAPH_PASSWORD_ENV",
    }
    assert all(value for value in supplied.values()), (
        "a value the script reads is supplied empty"
    )


# ── 3. a proof draft is not evidence ────────────────────────────────────────


def test_a_proof_draft_is_never_read_as_evidence(tmp_path):
    """`run` wrote one and then refused it, blaming the collector.

    "the evidence does not match the schema. This is a defect in the collector"
    -- and it was a defect in the list of names that are not evidence, which
    existed in two places and knew about one name. Both walkers read one list
    now, and this asserts the property at both.
    """
    from m365_governance import cli

    (tmp_path / "real.json").write_text("{}", encoding="utf-8")
    (tmp_path / "live-proof-draft.json").write_text("{}", encoding="utf-8")
    (tmp_path / "collection-manifest.json").write_text("{}", encoding="utf-8")

    for found in (collecting._files(tmp_path), cli._evidence_documents(tmp_path)):
        names = {path.name for path in found}
        assert names == {"real.json"}, (
            f"a collector's own bookkeeping was read as evidence: {sorted(names)}"
        )


def test_the_names_that_are_not_evidence_are_declared_once():
    """Two copies of this rule is how the first one went out of date."""
    assert "live-proof-draft" in collecting.NOT_EVIDENCE
    assert "collection-manifest" in collecting.NOT_EVIDENCE


# ── 4. a filtered read has to be a legal request ────────────────────────────


def test_an_odata_filter_is_encoded_before_it_is_sent():
    """`$filter=roleDefinitionId eq '62e9...'` has spaces in it.

    Python refuses to send it -- `URL can't contain control characters` -- so
    the read that counts a directory's Global Administrators had never worked
    against any tenant. No test found it because no test makes a request.
    """
    path = (
        "roleManagement/directory/roleAssignments"
        "?$filter=roleDefinitionId eq '62e90394-69f5-4237-9190-012177145e10'"
        "&$select=id,principalId"
    )
    encoded = graph.GraphReader._encoded(path)

    assert " " not in encoded, "the query would be refused before it is sent"
    assert encoded.startswith("roleManagement/directory/roleAssignments?"), (
        "the path was encoded along with the query"
    )
    # The characters OData gives meaning to survive: encoding them would change
    # the request rather than transport it.
    for meaningful in ("$filter=", "&$select=", "'", ","):
        assert meaningful in encoded, f"`{meaningful}` was encoded away"


def test_a_path_with_no_query_is_left_exactly_as_it_was():
    assert graph.GraphReader._encoded("policies/authorizationPolicy") == (
        "policies/authorizationPolicy"
    )


# ── 5. the connection summary must survive what a real one returns ──────────


def test_a_null_in_the_scope_list_does_not_take_the_summary_down():
    """A certificate connection returns one, and `describe` joined it.

    Authentication established, session opened, and then a TypeError while
    printing what had been achieved. Nothing was wrong with the connection.
    """
    connection = connecting.Connection(
        requested={},
        reach=connecting.Reach.ESTABLISHED,
        established={
            "host": "contoso.sharepoint.com",
            "client_id": APPLICATION["client_id"],
            "identity_kind": "application",
            "connection_type": "TenantAdmin",
            "scopes": [None, "", "AllSites.Read"],
            "observed_tenant_id": None,
        },
        address={},
        access={},
        because=[],
        returncode=0,
        seconds=0.4,
        attempted_at="2026-08-24T17:00:00Z",
    )
    record = connecting.document(connection)
    assert record["session"]["scopes"] == ["AllSites.Read"], (
        "a null survived into the record, where a sentence will join it"
    )

    # And the sentence itself is produced without raising, which is the fault
    # as it was actually met: the connection succeeded and the summary died.
    assert "application" in connecting.describe(connection)


def test_the_reason_and_the_record_agree_about_what_signed_in():
    """One screen said `identity application` and `a delegated session`.

    The wrong half was the one under `Because:`, which is where a reader goes
    when they doubt the other. The scope count disagreed for the same reason:
    the reason counted a null the record had dropped.
    """
    reasons = connecting._because(
        connecting.Reach.ESTABLISHED,
        returncode=0,
        cancelled=False,
        established={
            "url": "https://contoso-admin.sharepoint.com/",
            "identity_kind": "application",
            "scopes": [None],
        },
        lines=[],
    )
    joined = " ".join(reasons)
    assert "an application session" in joined, joined
    assert "delegated" not in joined, joined
    assert "no scopes were reported" in joined, (
        "the reason counted a scope the record does not carry"
    )


# ── 6. a Graph slice leaves the proof a PowerShell slice leaves ─────────────


def test_the_graph_path_records_a_proof_like_every_other_collector():
    """Without it a collector reads a real directory and publishes as untested.

    The writer was remembered for one of the two collectors, so
    `tenant-governance` and `conditional-access` could be run against a real
    tenant, return real evidence, decide forty-three rules, and still be
    published as never live tested. The registry was not wrong; nothing had
    ever told it.
    """
    from m365_governance import graph_slice

    source = Path(graph_slice.__file__).read_text(encoding="utf-8")
    assert "write_proof_draft" in source, (
        "the Graph collection path no longer records a proof, so nothing it "
        "does can raise a capability out of `none`"
    )
    assert callable(collecting.write_proof_draft)
