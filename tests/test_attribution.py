"""The eight cases `docs/ATTRIBUTION.md` says the contract must distinguish.

Written before the schema, because a schema chosen first decides which cases
exist. Each one is a state a reader can be in, and the point of the exercise is
that the artefact tells them which -- rather than one of them being silently
rendered as another.
"""

from m365_governance import attribution, composing, identity

SITE = {"kind": "site", "native_id": "s1"}


def document(collector: str, when: str, **facts) -> dict:
    return {
        "resource": dict(SITE),
        "facts": {
            name: {"state": "observed", "value": value} for name, value in facts.items()
        },
        "provenance": {"collector": collector, "collected_at": when},
        "coverage": {},
    }


def result(outcome: str, *paths, state: str = "observed") -> dict:
    return {
        "outcome": outcome,
        "evidence_used": [{"path": path, "state": state} for path in paths],
    }


# ---------------------------------------------------------------------------
# 1 and 2 · one acquisition, and two
# ---------------------------------------------------------------------------


def test_a_rule_depending_on_one_acquisition_resolves_to_one():
    [(_, attributed)] = composing.composed(
        [document("spo-collector", "09:00", permissions=17)]
    )

    links = attribution.chain(
        result("fail", "permissions.unique_scope_count"), attributed
    )

    assert len(links) == 1
    assert links[0]["paths"] == ["permissions.unique_scope_count"]
    assert not attribution.unresolved(links)


def test_a_rule_depending_on_two_acquisitions_resolves_to_both():
    """NO OWNERSHIP INVENTED AND NO FIRST-WINS.

    A one-to-one relation between a conclusion and a collector is the tidy
    answer the evidence does not support, and asserting it to make something
    downstream simpler is exactly the second authority this product removes.
    """
    [(_, attributed)] = composing.composed(
        [
            document("spo-collector", "09:00", items=148000),
            document("spo-collector", "09:05", permissions=17),
        ]
    )

    links = attribution.chain(
        result("fail", "items.count", "permissions.inheritance_broken"), attributed
    )

    assert len(links) == 2, "a rule reading two acquisitions resolves to two"
    assert sorted(p for link in links for p in link["paths"]) == [
        "items.count",
        "permissions.inheritance_broken",
    ]


# ---------------------------------------------------------------------------
# 3 · the case that kills every name-based approach
# ---------------------------------------------------------------------------


def test_two_acquisitions_sharing_a_collector_identity_stay_distinct():
    """Eleven SharePoint slices all publish `spo-collector`.

    Any attribution keyed by a collector name is wrong in exactly the case that
    matters, and would look correct everywhere else. The key is a digest over
    the document's canonical bytes.
    """
    a = document("spo-collector", "09:00", owners=1)
    b = document("spo-collector", "09:05", sharing=2)

    [(_, attributed)] = composing.composed([a, b])

    assert attributed["owners"] != attributed["sharing"]
    assert identity.document_digest(a) == attributed["owners"]
    assert identity.document_digest(b) == attributed["sharing"]


# ---------------------------------------------------------------------------
# 4 · collected, and nobody read it
# ---------------------------------------------------------------------------


def test_evidence_nobody_consumed_is_a_third_state():
    """Acquired, entered evaluation, not consumed.

    Distinct from not acquired and distinct from consumed. A product that
    collapsed it into either would be describing a collector that ran and was
    ignored exactly as it describes one that never ran.
    """
    [(_, attributed)] = composing.composed(
        [
            document("spo-collector", "09:00", items=148000),
            document("spo-collector", "09:05", spfx=3),
        ]
    )

    links = attribution.chain(result("fail", "items.count"), attributed)
    consumed = {link["document"] for link in links}

    assert len(attributed) == 2
    assert len(consumed) == 1
    untouched = set(attributed.values()) - consumed
    assert len(untouched) == 1, "the collected-and-unread block must be visible"


# ---------------------------------------------------------------------------
# 5 · no attribution at all
# ---------------------------------------------------------------------------


def test_evidence_with_no_attribution_says_so_and_is_never_proven():
    """An assessment produced before this existed, or assembled by hand.

    `attribution-unavailable` is the answer, explicitly and per link. Silence
    would be read as "no dependency", which is the opposite of what is true.
    """
    links = attribution.chain(result("fail", "permissions.unique_scope_count"), None)

    assert links and links[0]["document"] == attribution.UNATTRIBUTED
    assert attribution.unresolved(links) == [attribution.UNATTRIBUTED]


def test_a_path_no_table_entry_covers_is_named_separately():
    """Different from having no table at all, and reported as different.

    A table that exists and does not cover a path is a defect in the
    composition; a table that does not exist is an older artefact. Collapsing
    them would send somebody to look in the wrong place.
    """
    links = attribution.chain(result("fail", "ghost.count"), {"items": "sha256:aaaa"})

    assert attribution.unresolved(links) == [attribution.UNKNOWN_BLOCK]


# ---------------------------------------------------------------------------
# 6 and 7 · unknown with a cause, and nothing ran
# ---------------------------------------------------------------------------


def test_an_unknown_resolves_to_the_acquisition_that_tried():
    """So a reader learns WHY it is unknown, not only that it is.

    The evidence path was still addressed; the fact behind it was missing. The
    chain resolves, the state on the link says `missing`, and the outcome is
    not a conclusion.
    """
    [(_, attributed)] = composing.composed(
        [document("spo-collector", "09:00", permissions=17)]
    )

    unknown = result("unknown", "permissions.unique_scope_count", state="missing")
    links = attribution.chain(unknown, attributed)

    assert len(links) == 1
    assert links[0]["states"] == ["missing"]
    assert not attribution.decided(unknown), "an unknown is not a conclusion"


def test_zero_rules_leaves_no_chain_and_that_is_not_a_failure():
    assert attribution.chain({"outcome": "pass", "evidence_used": []}, {}) == []


def test_an_unknown_is_not_a_decision_and_a_pass_is():
    """`unknown` and `invalid_evidence` are outcomes this product is proud of
    and they are not conclusions about a tenant. A stage raised on them would
    claim rules decided something when what they decided is that they could
    not."""
    assert attribution.decided(result("fail", "items.count"))
    assert attribution.decided(result("pass", "items.count"))
    assert not attribution.decided(result("unknown", "items.count"))
    assert not attribution.decided(result("invalid_evidence", "items.count"))
    assert not attribution.decided(result("not_applicable", "items.count"))


# ---------------------------------------------------------------------------
# is this granularity NECESSARY, or only elegant?
# ---------------------------------------------------------------------------


def test_the_coarser_models_cannot_answer_and_this_is_why_they_are_refused():
    """THE NECESSITY PROOF, and it is a falsification rather than an argument.

    Three candidate relations could carry attribution into the artefact:

        finding      -> collector
        assessment   -> collector
        fact block   -> evidence document

    The first two are cheaper and would have looked fine on every fixture in
    this repository. This constructs the case they cannot answer and shows the
    third answering it, so the choice is demonstrated rather than preferred.

    ONE EVALUATION, TWO ACQUISITIONS, ONE COLLECTOR NAME. A rule reads the item
    count and whether inheritance is broken; the two facts were acquired by two
    separate runs of the SharePoint collector, minutes apart, and both publish
    `provenance.collector = "spo-collector"`.

    Ask the question a reader actually asks -- *which observation established
    that this library holds 148,000 items?* -- and:

      * `finding -> collector` answers `spo-collector`, which is true and
        useless: it names something that ran twice and does not say which run,
        so the reader cannot reach the population, the moment or the identity
        behind the number they are being asked to act on.

      * `assessment -> collector` is worse: it answers with the set of every
        collector that contributed to the whole document, which for a real
        assessment is most of them.

      * `fact block -> evidence document` answers with one document, and from
        that document the collector, the acquisition, the moment, the identity
        kind and the population all follow. **The collector is derived from the
        link and is not the link**, which is the whole distinction: a collector
        is implementation, and an evidence document is a thing that happened.
    """
    early = document("spo-collector", "2026-08-17T09:00:00Z", items=148000)
    later = document("spo-collector", "2026-08-17T09:05:00Z", permissions=17)

    [(_, attributed)] = composing.composed([early, later])

    finding = result("fail", "items.count", "permissions.inheritance_broken")

    # The two coarser models, built the way somebody would have built them.
    by_finding = {doc["provenance"]["collector"] for doc in (early, later)}
    by_assessment = by_finding

    assert by_finding == {"spo-collector"}, (
        "`finding -> collector` collapses two acquisitions into one name, so "
        "it cannot say which run established the count"
    )
    assert by_assessment == by_finding, (
        "`assessment -> collector` is the same answer with a wider scope, and "
        "answers a narrower question no better"
    )

    # The proposed relation, asked the same question.
    links = attribution.chain(finding, attributed)
    counted = [link for link in links if "items.count" in link["paths"]]

    assert len(counted) == 1, "the count resolves to exactly one acquisition"
    assert counted[0]["document"] == identity.document_digest(early)
    assert counted[0]["document"] != identity.document_digest(later)

    # And the chain reaches the ORIGINAL observation, not a name: everything a
    # reader needs is on the document the link points at.
    reached = {identity.document_digest(d): d for d in (early, later)}[
        counted[0]["document"]
    ]
    assert reached["provenance"]["collected_at"] == "2026-08-17T09:00:00Z"
    assert set(reached["facts"]) == {"items"}


def test_a_single_evaluation_stays_unambiguous_across_both_acquisitions():
    """The condition set for proceeding: one evaluation, two acquisitions, and
    the chain unambiguous to BOTH original observations.

    Not one of them, and not a set the reader has to disambiguate. Each path
    resolves to its own document, and the two documents are different things.
    """
    early = document("spo-collector", "2026-08-17T09:00:00Z", items=148000)
    later = document("spo-collector", "2026-08-17T09:05:00Z", permissions=17)

    [(_, attributed)] = composing.composed([early, later])
    links = attribution.chain(
        result("fail", "items.count", "permissions.inheritance_broken"), attributed
    )

    by_path = {path: link["document"] for link in links for path in link["paths"]}

    assert by_path["items.count"] == identity.document_digest(early)
    assert by_path["permissions.inheritance_broken"] == identity.document_digest(later)
    assert not attribution.unresolved(links)
