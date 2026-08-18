"""One resource, however many collectors described it.

Every case here came from running the product against a real tenant on
2026-08-18, where nine slices collected cleanly and no assessment could be
built from them.
"""

from __future__ import annotations

import json

import pytest

from m365_governance import composing
from m365_governance.resources import packaged

FIXTURES = packaged("fixtures") / "sharepoint"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_two_slices_of_one_site_become_one_document():
    """What `collect owners` and `collect sharing` produce, assessed together.

    This is the shape the pipeline could not carry: two documents, one
    resource, and a run set that holds one run per resource. The only way
    through was to merge the files by hand.
    """
    owners = _load("site-owners-group-not-expanded")
    sharing = _load("site-sharing-beside-owners")
    assert owners["resource"]["native_id"] == sharing["resource"]["native_id"]

    composed = composing.compose([owners, sharing])

    assert len(composed) == 1
    assert set(composed[0]["facts"]) == {"owners", "sharing"}


def test_the_composed_coverage_keeps_what_each_slice_said():
    """A union, and an absence one collector recorded is not cancelled by
    another collector succeeding at something else."""
    composed = composing.compose(
        [_load("site-owners-group-not-expanded"), _load("site-sharing-beside-owners")]
    )[0]

    assert set(composed["coverage"]["requested"]) == {"owners", "sharing"}
    assert "owners" in composed["coverage"]["unavailable"]
    assert composed["coverage"]["unavailable"]["owners"]["state"] == "partial"


def test_a_resource_described_once_is_untouched():
    only = _load("site-two-owners")
    assert composing.compose([only]) == [only]


def test_the_same_fact_block_twice_is_refused_even_when_identical():
    """Identical or not, one of them would be dropped.

    Composing it silently is fine only if the caller really did mean to supply
    the same evidence twice, and nothing here can promise that.
    """
    document = _load("site-two-owners")
    with pytest.raises(composing.Conflict) as caught:
        composing.compose([document, json.loads(json.dumps(document))])
    assert "`owners`" in str(caught.value)
    assert "identically" in str(caught.value)


def test_two_collectors_disagreeing_are_refused_rather_than_reconciled():
    a = _load("site-two-owners")
    b = json.loads(json.dumps(a))
    b["facts"]["owners"]["effective_count"] = 99
    with pytest.raises(composing.Conflict) as caught:
        composing.compose([a, b])
    assert "differently" in str(caught.value)


# ---------------------------------------------------------------------------
# the other three defects the first real run exposed
# ---------------------------------------------------------------------------


def test_a_rule_the_collection_never_asked_is_not_reported_as_unknown():
    """1,668 lines, of which 742 said only "this document does not carry that".

    The site inventory slice collects storage. It was never going to say
    whether a sensitivity label is applied, and 53 findings saying so buried
    the 53 that meant something. A rule whose evidence namespace is absent was
    not asked; a rule whose namespace is present and absent-stated WAS asked
    and failed, and that is still `unknown`.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rules

    rules = [r.data for r in load_rules(packaged("rules"))]
    storage_only = _load("site-storage-comfortable")

    every = engine.evaluate(rules, storage_only)
    asked = engine.evaluate(rules, storage_only, only_collected=True)

    assert len(asked.results) < len(every.results), "scoping selected nothing"
    assert {r.rule_id for r in asked.results} <= {r.rule_id for r in every.results}
    # Nothing that was asked changed its answer.
    by_id = {r.rule_id: r.outcome for r in every.results}
    assert all(by_id[r.rule_id] == r.outcome for r in asked.results)


def test_a_collector_that_tried_and_failed_still_reports_unknown():
    """The scoping must not launder a refusal into silence.

    `spfx` refused by a permission writes the namespace with an absent state.
    That is a genuine unknown about the resource and has to survive.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rules

    rules = [r.data for r in load_rules(packaged("rules"))]
    tried_and_failed = _load("site-spfx-tenant-catalog-not-comparable")

    run = engine.evaluate(rules, tried_and_failed, only_collected=True)
    spfx = [r for r in run.results if r.rule_id == "SPO-SPFX-001"]
    assert spfx, "the rule was dropped although the collector wrote its namespace"
    assert spfx[0].outcome.value == "unknown"


def test_the_report_says_the_resource_class_is_not_an_outcome():
    """A real report opened with `unknown 53` directly above `Unknown 0`.

    One is a resource whose kind the classifier could not settle; the other is
    a rule that could not be decided. Printed as neighbours in the same
    vocabulary, with no label, the first number a reader sees is the wrong one.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rules
    from m365_governance.reporting import many_to_markdown
    from m365_governance.results import RunSet

    rules = [r.data for r in load_rules(packaged("rules"))]
    run = engine.evaluate(rules, _load("site-two-owners"))
    rendered = many_to_markdown(RunSet([run]))
    assert "which is not an outcome" in rendered


def test_an_unexpanded_group_reaches_the_coverage():
    """The facts said so and the coverage did not.

    On a real site the only administrator was a group nobody expanded, and the
    document reported the slice complete. A reader distinguishing "there is
    nobody" from "I could not see who" had nothing to read.
    """
    owners = _load("site-owners-group-not-expanded")
    assert owners["facts"]["owners"]["expansion_complete"] is False
    assert owners["coverage"]["completed"] == []
    assert owners["coverage"]["unavailable"]["owners"]["state"] == "partial"


def test_an_owner_an_identity_cannot_see_is_not_an_owner_that_is_absent():
    """A confident, actionable, wrong finding, with remediation attached.

    FOUND BY RUNNING THE SAME COLLECTION TWICE, once as a person and once as
    the application. `Get-PnPSiteCollectionAdmin` returned nothing under an
    application-only identity holding Sites.Read.All, on a site whose
    administrator the delegated read saw in the same minute: a Microsoft 365
    group. It did not raise, so nothing was caught, and the count went out as
    an EXACT zero with the expansion marked complete. SPO-SITE-001 reported
    `The site has 0 owner` and told an administrator to go and fix a site that
    was fine.

    A collector never turns a denial into an empty tenant, and it cannot tell
    an unreadable administrator from an absent one, so zero is not published as
    a count.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rule

    evidence = _load("site-owners-unreadable-by-application")
    assert evidence["provenance"]["identity_kind"] == "application"
    assert evidence["facts"]["owners"]["state"] == "partial"
    assert "effective_count" not in evidence["facts"]["owners"]

    rule = load_rule(packaged("rules") / "sharepoint" / "SPO-SITE-001.yaml").data
    assert engine._evaluate(rule, evidence).outcome.value == "unknown"


# ---------------------------------------------------------------------------
# identity is part of the evidence
# ---------------------------------------------------------------------------


def test_two_identities_read_one_site_and_see_different_things():
    """Not an authentication detail. A property of the trust model.

    The same collector, the same site, the same minute, and two identities:
    a person saw a Microsoft 365 group administering it, and the application
    saw nothing at all. No API raised. Nothing was misconfigured. What differs
    is what each identity is permitted to resolve, and an evidence document
    that did not say which one produced it would describe part of an estate in
    language that suits the whole of one.

    Both fixtures are sanitized observations of the same site on 2026-08-18.
    """
    person = _load("site-owners-group-not-expanded")
    application = _load("site-owners-unreadable-by-application")

    assert person["resource"]["native_id"] == application["resource"]["native_id"]
    assert person["provenance"]["identity_kind"] == "delegated"
    assert application["provenance"]["identity_kind"] == "application"
    assert application["provenance"]["identity_method"] == "certificate"

    # The same question, answered from two identities, and they do not agree
    # about what is there. That is the finding, not a defect.
    assert person["facts"]["owners"]["group_count"]["value"] == 1
    assert application["facts"]["owners"]["state"] == "partial"


def test_neither_identity_produces_a_confident_wrong_answer():
    """Different visibility is honest; a confident answer from it is not."""
    from m365_governance import engine
    from m365_governance.loader import load_rule

    rule = load_rule(packaged("rules") / "sharepoint" / "SPO-SITE-001.yaml").data
    for name in (
        "site-owners-group-not-expanded",
        "site-owners-unreadable-by-application",
    ):
        outcome = engine._evaluate(rule, _load(name)).outcome.value
        assert outcome == "unknown", f"{name} decided the owner count: {outcome}"


def test_every_document_says_which_identity_produced_it():
    """Required by the contract, not by convention.

    It was hard-coded to `delegated` and nothing would have failed the day an
    application-only run wrote evidence describing itself as one person's view.
    """
    import json as _json

    schema = _json.loads(
        (packaged("schemas") / "evidence.schema.json").read_text(encoding="utf-8")
    )
    provenance = schema["$defs"]["provenance"]
    assert "identity_kind" in provenance["required"]
    assert set(provenance["properties"]["identity_method"]["enum"]) == {
        "interactive",
        "device-code",
        "certificate",
        "not-established",
    }


def test_no_document_carries_a_credential():
    """A client id names a registration somebody can look up. Everything else
    about the credential stays out of the evidence, in every fixture that ever
    came from a real run."""

    for path in (packaged("fixtures") / "sharepoint").glob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        for secret in ("begin private key", "begin rsa", ".pfx", "certificatepassword"):
            assert secret not in text, f"{path.name} carries {secret}"


def test_every_observation_fixture_says_how_it_authenticated():
    """One of them did not, and the gate above still passed.

    `site-owners-group-not-expanded` was sanitized from a run taken before
    `identity_method` existed, so the pair meant to demonstrate that identity
    is part of the evidence had it on one side only. The schema does not
    require the field -- an imported document may genuinely not know -- but a
    fixture this repository collected itself always does.
    """
    import json as _json

    registry = _json.loads(
        (packaged("fixtures").parent / "fixture-registry.json").read_text(
            encoding="utf-8"
        )
    )
    observed = [
        entry["path"]
        for entry in registry["fixtures"]
        if entry["origin"] == "sanitized-observation"
    ]
    assert observed, "no observation fixtures at all"

    for relative in observed:
        document = _json.loads(
            (packaged("fixtures").parent / relative).read_text(encoding="utf-8")
        )
        provenance = document["provenance"]
        # Present, always. `not-established` is the honest value for a
        # fixture collected before the field existed, and it is the word this
        # product already has for evidence that does not carry its own
        # identity -- filling it in from memory would be worse.
        assert provenance.get("identity_method"), f"{relative}: no identity_method"
        assert provenance.get("identity_kind"), f"{relative}: no identity_kind"


# ---------------------------------------------------------------------------
# a rule that could not be near a limit nobody set
# ---------------------------------------------------------------------------


def test_a_site_at_the_platform_maximum_has_no_limit_to_be_near():
    """53 passes, each one 0 per cent of a quota nobody chose.

    Microsoft documents 25 TB as the maximum storage per site collection, and
    documents that switching to pooled storage `resets all the limits to
    25 TB`. So a site carrying exactly that is not a site with a generous
    limit: it is a site with none, drawing from the organisation's pool. The
    rule divided by it anyway and reported that everything was fine.

    A pass says the question was asked and the answer was good. There was no
    question.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rule

    rule = load_rule(packaged("rules") / "sharepoint" / "SPO-SITE-003.yaml").data
    pooled = _load("site-storage-comfortable")
    pooled["facts"]["site"]["storage_quota_mb"]["value"] = 26214400
    pooled["facts"]["site"]["storage_limit_set"]["value"] = False

    assert engine._evaluate(rule, pooled).outcome.value == "not-applicable"


def test_the_rule_still_decides_where_a_limit_was_set():
    """Adjudicating it must not blunt it: a manual limit is where it earns its
    place, and that tenant is the one it was written for."""
    from m365_governance import engine
    from m365_governance.loader import load_rule

    rule = load_rule(packaged("rules") / "sharepoint" / "SPO-SITE-003.yaml").data
    for name, expected in (
        ("site-storage-comfortable", "pass"),
        ("site-storage-nearly-full", "fail"),
        ("site-storage-no-quota", "not-applicable"),
    ):
        assert engine._evaluate(rule, _load(name)).outcome.value == expected, name


def test_a_resource_with_nothing_to_read_does_not_fill_the_report():
    """Making the rule honest made the document ten times worse.

    The report collapsed a group only when every result was a PASS, so 53
    sites that had gone from `pass` to `not-applicable` went from one line to
    279 of the identical paragraph. `attention` already puts both outcomes in
    `settled`; the report was not asking it.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rules
    from m365_governance.reporting import many_to_markdown
    from m365_governance.results import RunSet

    rules = [r.data for r in load_rules(packaged("rules"))]
    pooled = _load("site-storage-comfortable")
    pooled["facts"]["site"]["storage_quota_mb"]["value"] = 26214400
    pooled["facts"]["site"]["storage_limit_set"]["value"] = False

    rendered = many_to_markdown(
        RunSet([engine.evaluate(rules, pooled, only_collected=True)])
    )
    assert "nothing to read" in rendered
    assert "nothing but passes" not in rendered, (
        "the collapse still claims passes it did not have"
    )
    assert "No storage limit is set on this site" not in rendered, (
        "a settled resource was printed in full"
    )


# ---------------------------------------------------------------------------
# two rules about a missing label, and they are not the same one
# ---------------------------------------------------------------------------


def test_the_two_classification_rules_are_not_duplicates():
    """They fire together on a real site, and they are still two decisions.

    Asked because both reported on one site in a real assessment, which is what
    duplication looks like from the outside. Across the shipped cases they
    agree five times and diverge five, because they read different facts and
    speak about different populations: SPO-CLASS-001 asks whether ANYTHING on
    the site records what it holds, and a classic classification string answers
    it; SPO-CLASS-003 asks whether the group's privacy and guest access are
    pinned, and a string cannot do that.

    The decisive case is a site with a classification string and no label. If
    the two were one rule, one of those answers would have to be wrong.
    """
    from m365_governance import engine
    from m365_governance.loader import load_rule

    one = load_rule(packaged("rules") / "sharepoint" / "SPO-CLASS-001.yaml").data
    three = load_rule(packaged("rules") / "sharepoint" / "SPO-CLASS-003.yaml").data

    legacy = _load("site-class-legacy-string")
    assert legacy["facts"]["classification"]["classification_set"]["value"] is True
    assert legacy["facts"]["classification"]["label_applied"]["value"] is False
    # A string satisfies one and says nothing to the other.
    assert engine._evaluate(one, legacy).outcome.value == "pass"

    # And where they do coincide, the message says what the second one adds,
    # so a reader seeing two findings knows why there are two.
    both = _load("site-class-group-unlabelled")
    assert engine._evaluate(one, both).outcome.value == "fail"
    result = engine._evaluate(three, both)
    assert result.outcome.value == "fail"
    assert "SPO-CLASS-001" in result.message
