"""A broader authority never receives less disclosure than a narrower one.

THE DEFECT, AND WHY IT WAS NOT A TYPO. Four renderers each carried their own
`if identity_kind == "delegated"` with their own sentence, written at different
times. `delegated` -- the NARROWER authority, which sees what one person sees
-- was disclosed in all four. `application` -- which reads whatever the tenant
granted the application, and is bounded by no person's view -- was named in one
of the four and silently absent from the other three.

Nobody decided that. Each renderer decided separately, and the ones written
when only delegated existed were never revisited when application arrived. A
report produced by an application with tenant-wide read permissions said
nothing at all about the identity that produced it, in three of four formats.

Two run-set renderers had a second form of it: they asked `any(kind ==
"delegated")`, so a set holding one delegated run and nine application ones
disclosed the delegated one and said nothing about the nine.

The owner is `connection/1.1.0` and `provenance.identity_kind`, and no second
registry was created for this. `reporting.IDENTITY` is a presentation of that
enum, and the first test below is what keeps it a presentation rather than a
second list that drifts.
"""

from __future__ import annotations

import json

import pytest

from m365_governance import reporting, resources
from m365_governance.results import Outcome, Result, Run, RunSet


def _enum() -> list[str]:
    """The published vocabulary, read from the contract rather than recalled."""
    schema = json.loads(
        (resources.packaged("schemas") / "connection.schema.json").read_text(
            encoding="utf-8"
        )
    )

    def find(node):
        if isinstance(node, dict):
            if "identity_kind" in node and isinstance(node["identity_kind"], dict):
                return node["identity_kind"].get("enum")
            for value in node.values():
                found = find(value)
                if found:
                    return found
        return None

    values = find(schema)
    assert values, "connection.schema.json no longer publishes identity_kind"
    return values


def _run(kind: str | None, n: int = 0) -> Run:
    provenance = {"collector": "spo-collector", "collected_at": "2026-08-23T09:00:00Z"}
    if kind is not None:
        provenance["identity_kind"] = kind
    return Run(
        resource={
            "workload": "sharepoint",
            "type": "site",
            "native_id": f"contoso,site,{n}",
            "display_name": f"Site {n}",
        },
        results=[
            Result(
                rule_id="SPO-LIST-001",
                rule_version="1.0",
                schema_version="1.0",
                resource_ref={"workload": "sharepoint", "type": "site"},
                outcome=Outcome.PASS,
                message="nothing to report",
                basis_type="convention",
                severity="low",
            )
        ],
        provenance=provenance,
        coverage={},
    )


def _render_all(kind: str | None) -> dict[str, str]:
    """The same evidence through all four paths a person can meet it in."""
    run = _run(kind)
    every = RunSet(runs=[run, _run(kind, 1)])
    return {
        "single markdown": reporting.to_markdown(run),
        "single html": reporting.to_html(run),
        "run-set markdown": reporting.many_to_markdown(every),
        "run-set html": reporting.many_to_html(every),
    }


def test_every_published_identity_kind_has_a_disclosure():
    """The table is a presentation of the contract, and this is what keeps it
    one. A value added to the enum with no line here would render through the
    fallback, which names it and establishes nothing -- honest, and not what
    anybody wants shipped."""
    missing = [kind for kind in _enum() if kind not in reporting.IDENTITY]

    assert missing == [], (
        f"the published enum has {missing} and the disclosure table does not. "
        "A kind with no disclosure is the shape that hid `application` for as "
        "long as it did"
    )


@pytest.mark.parametrize("kind", ["delegated", "application", "not-established"])
def test_no_supported_identity_kind_renders_as_an_empty_disclosure(kind):
    """THE FIRST INVARIANT. Not one of the three may reach a reader as silence.

    `not-established` is included deliberately. It must not become an empty
    line, an absent warning, or a quiet fallback to delegated: it is the one
    case where a reader cannot bound what the assessment reached at all, and
    that is worth saying rather than skipping.
    """
    for where, rendered in _render_all(kind).items():
        label = reporting.IDENTITY[kind].label
        assert f"Identity: {label}" in rendered, (
            f"{where} says nothing about an identity of `{kind}`"
        )


def test_application_is_disclosed_wherever_delegated_is():
    """THE SECOND INVARIANT, and the defect this file is named for.

    Not the same words -- the two identities mean different things and should
    read differently. What is refused is one of them being disclosed in a
    format where the other is not, because the one that was missing is the one
    that reads more.
    """
    delegated = _render_all("delegated")
    application = _render_all("application")

    for where in delegated:
        assert "Identity:" in delegated[where], f"{where} lost the delegated case"
        assert "Identity:" in application[where], (
            f"{where} discloses a delegated identity and says nothing about an "
            "application one, which is the broader authority of the two"
        )


def test_a_mixed_run_set_discloses_every_identity_it_holds():
    """The run-set renderers asked whether ANY run was delegated.

    One delegated run among nine application ones produced a report warning
    about one person's view, with nothing said about the nine that were not
    bounded by any person at all.
    """
    mixed = RunSet(
        runs=[_run("delegated", 0)]
        + [_run("application", n) for n in range(1, 10)]
    )

    for rendered in (
        reporting.many_to_markdown(mixed),
        reporting.many_to_html(mixed),
    ):
        assert reporting.IDENTITY["delegated"].label in rendered
        assert reporting.IDENTITY["application"].label in rendered


def test_imported_evidence_still_says_who_observed_it():
    """The disclosure sat on the `elif` of the import branch.

    So imported evidence carried an import notice and no identity at all --
    and imported evidence is precisely where the identity that produced it is
    least likely to be known, which makes saying so more useful rather than
    less.
    """
    run = _run(None)
    run.provenance["acquisition"] = "imported"
    run.provenance["import_source"] = {"tool": "another tool"}

    rendered = reporting.to_markdown(run)

    assert "imported" in rendered.lower()
    assert f"Identity: {reporting.IDENTITY['not-established'].label}" in rendered


def test_an_unrecognised_kind_is_named_rather_than_dropped():
    """A future enum value must not vanish between the contract and the page.

    It renders through a fallback that names the value and establishes nothing
    about it, which is the honest shape for something this version has never
    been told the meaning of.
    """
    rendered = reporting.to_markdown(_run("workload-identity"))

    assert "workload-identity" in rendered
    assert "not established" in rendered.lower()


# ---------------------------------------------------------------------------
# the documentation, governed structurally and written by people
# ---------------------------------------------------------------------------

MARKERS = ("<!-- identity-modes:start -->", "<!-- identity-modes:end -->")


def _normative_block() -> str:
    import pathlib

    security = (
        pathlib.Path(__file__).resolve().parents[1] / "SECURITY.md"
    ).read_text(encoding="utf-8")
    start, end = MARKERS
    assert start in security and end in security, (
        "SECURITY.md no longer carries the marked identity block. Without it "
        "the document's account of what this tool can read is prose nothing "
        "compares against a contract, which is how it came to say both modes "
        "were delegated for as long as it did"
    )
    return security.split(start, 1)[1].split(end, 1)[0]


def test_the_security_document_names_every_identity_the_contract_publishes():
    """NOT A GREP FOR WORDS IN ARBITRARY ENGLISH.

    A test asserting `"application" in SECURITY.md` passes on a sentence that
    mentions applications while denying they authenticate, which is roughly
    what the document used to do. So the structural claim lives in a marked
    block and is checked against the enum; the prose around it is human and
    this test never reads it.
    """
    block = _normative_block()
    missing = [kind for kind in _enum() if f"`{kind}`" not in block]

    assert missing == [], (
        f"the contract publishes {missing} and the identity table in "
        "SECURITY.md does not list them"
    )


def test_the_security_document_does_not_describe_a_mode_the_contract_dropped():
    """The other direction. A mode removed from the contract but still
    documented is a promise about something that no longer exists."""
    import re

    documented = set(re.findall(r"^\| `([a-z-]+)` \|", _normative_block(), re.M))
    published = set(_enum())

    assert documented <= published, (
        f"SECURITY.md documents {documented - published}, which the contract "
        "does not publish"
    )


def test_read_only_and_least_privilege_are_kept_apart():
    """THE CLAIM THAT WILL BE USED COMMERCIALLY, and the one it is not.

    `Read-only by design` is true for every identity and is worth saying.
    `least privilege` is a property of the identity somebody configured, and an
    application with broad read permissions produces a report with broad reach
    while remaining entirely read-only. Reading the first as if it implied the
    second is the misunderstanding this paragraph exists to prevent, so its
    absence is a failure rather than a tidy-up.
    """
    import pathlib

    security = (
        pathlib.Path(__file__).resolve().parents[1] / "SECURITY.md"
    ).read_text(encoding="utf-8")

    assert "least privilege" in security
    assert "read-only" in security.lower()
