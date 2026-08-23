"""What was observed, by service and by area, and the counts that must not appear.

THE PRODUCT IS NOT A COLLECTION OF CHECKS AND SHOULD NOT INTRODUCE ITSELF AS
ONE. A reader opening a result needs which parts of Microsoft 365 were looked
at and how far each reading got, before any rule identifier.

Everything is derived. There is no branch per service, because a projection
needing one would be a fifth place to add a service -- and four such places
were found in a single afternoon.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

from m365_governance import services
from m365_governance.results import Run

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src" / "m365_governance" / "data" / "fixtures"

ACROSS = [
    "exchange/exchange-forwarding-remote-domains-allow.json",
    "licensing/tenant-usage-concealed.json",
    "sharepoint/list-catalog-over-hard-limit.json",
    "entra/entra-conditional-access-everyone-no-exclusion.json",
]


@pytest.fixture(scope="module")
def view():
    scratch = pathlib.Path(tempfile.mkdtemp())
    for name in ACROSS:
        source = FIXTURES / name
        (scratch / source.name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    out = scratch / "assessment.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "m365_governance.cli",
            "assess",
            "--evidence",
            str(scratch),
            "--out",
            str(out),
        ],
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    canonical = json.loads(out.read_text(encoding="utf-8"))["canonical"]
    runs = [Run.from_dict(r) for r in canonical["run_set"]["runs"]]
    return services.observed(runs, canonical["evidence"])


def test_every_service_the_evidence_names_is_present(view):
    named = {s["service"] for s in view["services"]}

    assert {"sharepoint", "exchange", "entra", "microsoft-365"} <= named


def test_a_conclusion_is_counted_in_the_area_it_was_decided_from(view):
    """Attribution, one level up. A result names the evidence paths it used and
    the first segment is the fact block, which is the area.

    THIS FOUND A COLLECTOR NAMING ONE THING TWICE. Conditional Access published
    coverage as `conditional-access-policies` and facts as
    `conditional_access_policies`, so the join matched nothing and the service
    reported evidence collected and no conclusions while three rules were
    deciding on it.
    """
    entra = next(s for s in view["services"] if s["service"] == "entra")
    policies = next(
        a for a in entra["areas"] if a["area"] == "conditional_access_policies"
    )

    assert policies["conclusions"] >= 1
    assert entra["conclusions"] == sum(a["conclusions"] for a in entra["areas"])


def test_evidence_with_no_rule_reads_as_evidence_and_not_as_zero(view):
    """THE HARD ONE, AND THE REASON THIS EXISTS.

    Licensing feeds no rule by a recorded decision. `0 conclusions` beside a
    service that was read properly looks like a failure and is the opposite, so
    the sentence says what happened instead of counting what did not.
    """
    licensing = next(s for s in view["services"] if s["service"] == "microsoft-365")

    assert licensing["conclusions"] == 0
    assert services.sentence(licensing).startswith("Evidence collected")
    assert "conclusion" in services.sentence(licensing)


def test_an_area_that_was_not_read_is_distinct_from_one_that_was_refused(view):
    """Three states that look alike on a screen. `dependency` is collected by
    nothing; `usage` was read and came back partial. A product collapsing them
    would describe a collector that never ran exactly as one that ran and could
    not answer."""
    licensing = next(s for s in view["services"] if s["service"] == "microsoft-365")
    by_area = {a["area"]: a["state"] for a in licensing["areas"]}

    assert by_area["dependency"] == "not-observed"
    assert by_area["usage"] == "partial"
    assert by_area["assignment"] == "observed"


def test_a_service_reports_its_weakest_area(view):
    """A service that read four things and could not read one is not observed.

    Reporting the strongest would be the aggregate this product refuses, in the
    place a reader looks first.
    """
    licensing = next(s for s in view["services"] if s["service"] == "microsoft-365")

    assert licensing["state"] == "not-observed"


def test_no_coverage_percentage_is_derivable_from_this(view):
    """`21 conclusions` is twenty-one conclusions.

    It is not twenty-one out of anything, because the denominator would be the
    number of questions somebody could have asked, which nobody knows. `D5`
    forbids the aggregate and a total beside a count is how one arrives.
    """
    body = json.dumps(view)

    for forbidden in ("percent", "percentage", "coverage_pct", "score", "total_rules"):
        assert forbidden not in body

    for service in view["services"]:
        assert "of" not in {*service} and "total" not in {*service}


def test_the_projection_has_no_branch_per_service():
    """The property, asserted against the source rather than hoped for.

    A projection naming a service is a projection that needs editing when a
    service arrives, and four such places were found in one afternoon.
    """
    source = (ROOT / "src" / "m365_governance" / "services.py").read_text(
        encoding="utf-8"
    )
    body = source.split('"""', 2)[-1]

    # DERIVED, BECAUSE THE GATE THAT HOLDS THIS PROPERTY CAUGHT THIS TEST
    # WRITING THE LIST OUT. A test asserting that nothing hard-codes the
    # services, by hard-coding the services, is the joke that writes itself.
    workloads = {
        json.loads(document.read_text(encoding="utf-8"))
        .get("resource", {})
        .get("workload")
        for document in FIXTURES.rglob("*.json")
        if '"workload"' in document.read_text(encoding="utf-8")
    } - {None}

    for service in sorted(workloads):
        assert f'"{service}"' not in body, (
            f"services.py names {service!r} in code. A service is the workload "
            "on a resource and an area is what the collector requested; "
            "neither is a special case."
        )
