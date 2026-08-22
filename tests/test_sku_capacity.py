"""What a SKU is, established before anything is added to anything.

`units_purchased` was removed from the licensing collector after it returned a
seven-figure total on a tenant with a few dozen assigned seats. The sum was
arithmetically correct — every `prepaidUnits.enabled` added together — and
meaningless, because those units do not all count the same thing.

**THE FIX IS NOT A FILTER.** Dropping the rows whose numbers look absurd decides
what a tenant holds by how the figures look, which is the same error with a
threshold in front of it. The tests here hold the opposite discipline: classify
what the read can settle, say `not established` where it cannot, and never
exclude a SKU for its size.
"""

from __future__ import annotations

import json

import pytest

from conftest import DATA

LICENSING = DATA / "fixtures" / "licensing"

#: The fixture built to carry one row of every class at once.
MIXED = LICENSING / "tenant-capacity-mixed.json"


def facts(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)["facts"]["licensing"]


def rows(path):
    return {row["sku"]: row for row in facts(path)["sku_capacity"]["value"]}


ELIGIBILITY = {"comparable", "not-comparable", "not-established"}
KINDS = {"user-assignable", "organisational", "not-established"}


def _observed(path) -> bool:
    """Whether this run read the subscriptions at all.

    A collection that reached nothing publishes no classification, which is not
    the same as classifying nothing: `tenant-graph-modules-absent` is a run
    where the modules were not there, and a summary of zeroes over it would say
    the tenant holds no SKUs.
    """
    return "value" in facts(path).get("skus", {})


#: Every licensing fixture where subscriptions were actually read.
FIXTURES = [path for path in sorted(LICENSING.glob("*.json")) if _observed(path)]

#: And the ones where nothing was read, which have their own rule.
UNREAD = [path for path in sorted(LICENSING.glob("*.json")) if not _observed(path)]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_every_sku_carries_a_classification_and_its_reason(path):
    """A row with no classification is a row somebody will add up anyway."""
    for sku, row in rows(path).items():
        assert row["capacity_kind"] in KINDS, sku
        assert row["aggregation_eligibility"] in ELIGIBILITY, sku
        assert row["because"], f"{sku} was classified with no reason given"


def test_a_company_sku_is_not_user_capacity():
    """Microsoft documents that only a SKU whose target class is `User` is
    assignable. A `Company` SKU's units were never user seats, and this is the
    one exclusion that rests on a documented property rather than a judgement.
    """
    row = rows(MIXED)["MCOMEETADV"]

    assert row["capacity_kind"] == "organisational"
    assert row["aggregation_eligibility"] == "not-comparable"
    assert any("only a SKU whose target class is User" in why for why in row["because"])


@pytest.mark.parametrize(
    "sku,status", [("EMS", "Warning"), ("VISIOCLIENT", "Suspended")]
)
def test_a_subscription_out_of_good_standing_is_not_current_capacity(sku, status):
    """`capabilityStatus` is a documented enumeration and only `Enabled` means
    the subscription is running. A tenant's expiring and cancelled units are
    real and are not capacity it currently has."""
    row = rows(MIXED)[sku]

    assert row["aggregation_eligibility"] == "not-comparable"
    assert any(status in why for why in row["because"])


def test_a_target_class_nobody_has_seen_is_not_guessed_at():
    """`appliesTo` outside the documented pair is not an error and not a licence
    to assume. The fixture's row carries nearly ten million units, which is
    exactly the shape that invites a threshold."""
    row = rows(MIXED)["UNRECOGNISED_TARGET"]

    assert row["capacity_kind"] == "not-established"
    assert any("not a documented target class" in why for why in row["because"])


def test_a_sku_is_never_excluded_for_the_size_of_its_number():
    """THE TEST THIS SLICE EXISTS FOR.

    `POWER_BI_STANDARD` carries a million units in the fixture and it is
    classified exactly like `ENTERPRISEPACK`, which carries five hundred. From
    this surface the two are indistinguishable, and that indistinguishability
    is the finding — not a problem to be tidied away with `enabled < 100000`.
    """
    million = rows(MIXED)["POWER_BI_STANDARD"]
    hundreds = rows(MIXED)["ENTERPRISEPACK"]

    assert million["capacity_kind"] == hundreds["capacity_kind"]
    assert million["aggregation_eligibility"] == hundreds["aggregation_eligibility"]

    skus = {row["sku"]: row for row in facts(MIXED)["skus"]["value"]}
    assert skus["POWER_BI_STANDARD"]["prepaid_units"]["enabled"] == 1_000_000

    # And every SKU observed appears in the classification. A row that vanished
    # would be an exclusion nobody could see.
    assert set(skus) == set(rows(MIXED))


def test_no_sku_is_comparable_from_this_surface_alone():  # noqa: D401
    """The result, and it is not a gap in the implementation.

    Nothing on `subscribedSkus` establishes that a SKU's units are seats the
    organisation bought. Microsoft documents self-service sign-up as
    provisioning services without an administrator acting, so a SKU's presence
    is not a purchase; and `prepaidUnits.enabled` is documented as the units
    enabled for the active subscription, which is a different quantity from the
    seats a subscription carries.
    """
    for path in FIXTURES:
        licensing = facts(path)
        if licensing["subscription_surface"]["value"] == "observed":
            continue  # The commercial surface was read; that case is below.
        summary = licensing["capacity_summary"]["value"]

        assert summary["comparable"] == 0, path.stem
        assert all(
            row["aggregation_eligibility"] != "comparable"
            for row in rows(path).values()
        ), path.stem


def test_the_figure_everybody_wants_is_absent_and_names_its_measurement():
    """`not established` with the next measurement named, never an estimate.

    `companySubscription` carries `isTrial` — whether the subscription is a free
    trial or purchased — and `totalLicenses` — the seats it includes. It is on
    `/directory/subscriptions`, beta only, and `subscribedSku.subscriptionIds`
    is the join.
    """
    for path in FIXTURES:
        licensing = facts(path)
        if licensing["subscription_surface"]["value"] == "observed":
            continue
        absent = licensing["comparable_capacity"]

        assert absent["state"] == "missing"
        assert "value" not in absent
        for named in (
            "companySubscription",
            "isTrial",
            "totalLicenses",
            "/directory/subscriptions",
            "subscriptionIds",
        ):
            assert named in absent["detail"], f"{path.stem} does not name {named}"


def test_the_counts_are_of_skus_and_never_of_units():
    """A count of rows means the same thing on every row. A sum of units does
    not, which is the whole finding — so the summary counts rows, and its total
    is the number of SKUs observed."""
    for path in FIXTURES:
        licensing = facts(path)
        summary = licensing["capacity_summary"]["value"]
        observed = licensing["subscribed_skus"]["value"]

        by_eligibility = sum(
            summary[state]
            for state in ("comparable", "not-comparable", "not-established")
        )
        by_kind = sum(
            summary[f"kind_{kind}"]
            for kind in ("user_assignable", "organisational", "not_established")
        )

        assert by_eligibility == observed, path.stem
        assert by_kind == observed, path.stem

        # AND THE COUNT IS OF THE ROWS ACTUALLY CARRIED. A fixture said the
        # tenant held fourteen subscriptions and listed three of them — a
        # document reporting on a subset in language that suited the whole,
        # which no consumer could have told apart from a complete reading.
        assert observed == len(licensing["skus"]["value"]), path.stem


@pytest.mark.parametrize("path", UNREAD, ids=lambda p: p.stem)
def test_a_run_that_read_nothing_classifies_nothing(path):
    """An empty summary is a claim. A run whose collector could not reach the
    directory has not established that the tenant holds no SKUs, and a
    `capacity_summary` of zeroes over it would say exactly that."""
    licensing = facts(path)

    assert "value" not in licensing.get("skus", {})
    assert "sku_capacity" not in licensing
    assert "capacity_summary" not in licensing


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_the_four_prepaid_counters_are_all_carried(path):
    """`prepaidUnits` is a `licenseUnitsDetail` with four counters, one per
    lifecycle state, and the collector used to read `enabled` alone. A tenant
    whose subscription has expired has its units in `warning`, and a single
    integer cannot say so."""
    for sku in facts(path)["skus"]["value"]:
        units = sku["prepaid_units"]

        assert set(units) == {"enabled", "warning", "suspended", "locked_out"}, sku[
            "sku"
        ]
        assert all(isinstance(count, int) for count in units.values()), sku["sku"]


JOINED = LICENSING / "tenant-capacity-joined.json"
UNSUPPORTED = LICENSING / "tenant-capacity-unsupported.json"


def test_the_commercial_surface_records_whether_it_was_read():
    """A run that did not ask and a tenant with nothing are the same nothing."""
    for path, state in [
        (JOINED, "observed"),
        (UNSUPPORTED, "unsupported"),
        (MIXED, "not-observed"),
    ]:
        licensing = facts(path)

        assert licensing["subscription_surface"]["value"] == state, path.stem
        assert licensing["subscription_surface_stability"]["value"] == "beta"


def test_the_join_says_which_of_its_five_states_it_reached():
    """`not-observed`, `unsupported`, `joined` and `unmatched` are four
    different answers, and only one of them is about the tenant."""
    joined = {row["sku"]: row for row in facts(JOINED)["subscription_join"]["value"]}

    assert joined["ENTERPRISEPACK"]["state"] == "joined"
    assert joined["ENTERPRISEPACK"]["seats"] == 500
    # Its subscriptions were asked for and not found. Evidence, not a gap.
    assert joined["EMS"]["state"] == "unmatched"
    assert "seats" not in joined["EMS"]

    absent = {row["sku"]: row for row in facts(MIXED)["subscription_join"]["value"]}
    assert all(row["state"] == "not-observed" for row in absent.values())

    refused = {
        row["sku"]: row for row in facts(UNSUPPORTED)["subscription_join"]["value"]
    }
    assert all(row["state"] == "unsupported" for row in refused.values())


def test_is_trial_false_is_never_read_as_purchased():
    """THE TRAP THE JOIN WALKS INTO, AND THE REASON IT DOES NOT CLOSE THIS.

    Microsoft documents `isTrial` as `whether the subscription is a free trial
    or purchased`, which reads as a binary and is not one in a tenant: a
    self-service free programme is neither. `FLOW_FREE` in this fixture is
    joined, reports `isTrial: false`, carries ten thousand seats, and nobody
    bought it.
    """
    rows_by_sku = {
        row["sku"]: row for row in facts(JOINED)["subscription_join"]["value"]
    }
    free = rows_by_sku["FLOW_FREE"]

    assert free["state"] == "joined"
    assert free["commercial_basis"] == "not-a-trial"
    assert any(
        "does not establish that any of them was bought" in why
        for why in free["because"]
    )

    # And no vocabulary anywhere says `purchased` of an observed value.
    assert facts(JOINED)["purchased_capacity"]["state"] == "not-supported"


def test_a_group_whose_basis_is_not_established_is_never_summed():
    """The product's own test: a mathematically correct number that induces a
    false reading is not published as a figure.

    The `not-a-trial` group here holds a bought subscription of five hundred
    seats and two free allocations of a million and ten thousand. Its sum is
    1,010,500 beside a tenant of a few hundred people, which is the removed
    total returned with a citation attached.
    """
    capacity = facts(JOINED)["comparable_capacity"]["value"]

    assert capacity["trial"]["seats"] == 25
    for basis in ("not-a-trial", "mixed", "not-established"):
        assert "seats" not in capacity[basis], basis
        assert "seats_not_summed" in capacity[basis], basis

    serialised = json.dumps(facts(JOINED))
    assert "1010500" not in serialised
    assert "1010560" not in serialised


def test_seats_are_comparable_and_that_is_a_claim_about_the_unit():
    """`comparable` says the units may be added, and says nothing about what
    was bought. Both are needed and neither implies the other."""
    classified = rows(JOINED)

    for sku in ("ENTERPRISEPACK", "SPE_E5", "FLOW_FREE"):
        assert classified[sku]["aggregation_eligibility"] == "comparable", sku
        assert any(
            "says nothing about whether they were bought" in why
            for why in classified[sku]["because"]
        ), sku

    # A Company SKU joins and stays out: the unit is not user seats.
    assert classified["MCOMEETADV"]["subscription_state"] == "joined"
    assert classified["MCOMEETADV"]["aggregation_eligibility"] == "not-comparable"
