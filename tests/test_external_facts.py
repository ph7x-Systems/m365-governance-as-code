"""Facts about things outside this repository, and where each one came from.

**Facts before design. Schema before mapping. Tenant before rule.**

Nothing external is implemented from memory, from a plausible-sounding name,
or from secondary documentation, when a schema, an assembly or a specification
exists and can be read. `tests/external/` is where those readings are kept, so
that a mapping written six months from now is checked against what the source
said rather than against what somebody recalls it saying.

These tests never reach the network. They enforce two things about the
recorded files themselves: that every fact is attributed, and that no code in
this repository uses a value the recording does not contain.

The rule exists because plausibility is not evidence. Asked in prose for the
permitted values of SARIF's `result.kind`, a summary of the specification
offered `redirect` and `hotspot`. Both sound entirely reasonable. Neither is
in the enum.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from conftest import ROOT

EXTERNAL = ROOT / "tests" / "external"

RECORDINGS = sorted(EXTERNAL.glob("*.json"))


def load(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_there_is_at_least_one_recording():
    """A directory nobody writes to is a rule nobody follows."""
    assert RECORDINGS, f"no recorded external facts under {EXTERNAL}"


@pytest.mark.parametrize("path", RECORDINGS, ids=lambda p: p.stem)
def test_every_recording_is_attributed(path):
    """An unattributed fact is indistinguishable from a remembered one.

    A url alone is not enough: the date is what tells a later reader whether
    the recording predates the version they are looking at.
    """
    recorded = load(path)
    for key in ("subject", "why_recorded", "source"):
        assert recorded.get(key), f"{path.name}: missing {key}"

    source = recorded["source"]
    for key in ("url", "kind", "publisher", "checked_at"):
        assert source.get(key), f"{path.name}: source is missing {key}"

    # An unparseable date is a date nobody can compare against a release.
    checked = dt.date.fromisoformat(source["checked_at"])
    assert checked <= dt.date(2100, 1, 1)

    # Secondary documentation is not a normative source. An article about a
    # specification is exactly what this rule exists to refuse.
    assert source["kind"] in {
        "json-schema",
        "specification",
        "assembly",
        "api-metadata",
        "product-response",
    }, f"{path.name}: {source['kind']} is not a normative kind of source"


@pytest.mark.parametrize("path", RECORDINGS, ids=lambda p: p.stem)
def test_every_recorded_enum_has_values(path):
    recorded = load(path)
    for name, enum in (recorded.get("enums") or {}).items():
        assert enum.get("values"), f"{path.name}: {name} recorded with no values"
        assert len(set(enum["values"])) == len(enum["values"]), (
            f"{path.name}: {name} has a duplicate value"
        )
        default = enum.get("default")
        assert default is None or default in enum["values"], (
            f"{path.name}: {name} default {default!r} is not one of its own values"
        )


@pytest.mark.parametrize("path", RECORDINGS, ids=lambda p: p.stem)
def test_a_gap_is_declared_and_never_filled_by_plausibility(path):
    """Where the source does not answer, the recording says so.

    A gap with no detail is worse than no gap at all: it looks like diligence
    and carries none of it.
    """
    for gap in load(path).get("gaps") or []:
        assert gap.get("question"), f"{path.name}: a gap with no question"
        assert gap.get("state") in {"unverified", "unanswerable"}
        assert len(gap.get("detail", "")) > 40, (
            f"{path.name}: gap '{gap.get('question')}' has no usable detail"
        )


def test_sarif_kinds_are_the_schemas_and_not_the_plausible_ones():
    """The recording that motivated this file.

    `redirect` and `hotspot` were offered by a prose summary of the
    specification. They are not in the schema's enum, and no future mapping may
    reach for them.
    """
    sarif = load(EXTERNAL / "sarif-2.1.0.json")
    kinds = set(sarif["enums"]["result.kind"]["values"])

    assert kinds == {
        "notApplicable",
        "pass",
        "fail",
        "review",
        "open",
        "informational",
    }
    assert "redirect" not in kinds
    assert "hotspot" not in kinds

    # The constraint that decides whether the slice is worth building at all
    # is recorded as unverified rather than assumed in either direction.
    gaps = {g["question"]: g["state"] for g in sarif["gaps"]}
    assert any("level" in q for q in gaps), (
        "the kind-to-level constraint must stay recorded until it is verified"
    )
    assert all(state == "unverified" for state in gaps.values())


def test_no_sarif_mapping_exists_yet():
    """Epic B5 is blocked on a decision, and this asserts the block holds.

    When a mapping is written, this test is what forces it to be written
    against the recorded enum: delete this and the next test replaces it, and
    the enum is what it checks against.
    """
    source = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py")
    )
    assert "sarif" not in source.lower(), (
        "a SARIF mapping appeared before the kind-to-level constraint was "
        "verified; see docs/EPIC-B.md, slice B5"
    )


# ---------------------------------------------------------------------------
# The recording that makes the rule retroactive
# ---------------------------------------------------------------------------

COLLECTOR = ROOT / "collectors" / "powershell" / "sharepoint" / "Get-SpoEvidence.ps1"

#: `Get-PnPSite -Includes X` loads a property of the CSOM type, so which type
#: each cmdlet returns decides which recorded set the names are checked
#: against.
RETURNS = {
    "Get-PnPSite": "Microsoft.SharePoint.Client.Site.properties",
    "Get-PnPWeb": "Microsoft.SharePoint.Client.Web.properties",
    "Get-PnPList": "Microsoft.SharePoint.Client.List.properties",
}


def includes_clauses() -> list[tuple[str, list[str]]]:
    """Every `-Includes` in the collector, with the cmdlet it belongs to.

    Line continuations are folded first: the modernity clause spans two lines,
    and a reader of the raw text would silently check half of it.
    """
    import re

    text = COLLECTOR.read_text(encoding="utf-8").replace("`\n", " ")
    found = []
    for match in re.finditer(r"(Get-PnP\w+)\s+-Includes\s+([A-Za-z0-9_,\s]+)", text):
        cmdlet, names = match.group(1), match.group(2)
        properties = [n.strip() for n in names.split(",") if n.strip()]
        # The last name runs into whatever followed the clause on that line.
        properties = [p.split()[0] for p in properties if p.split()]
        found.append((cmdlet, properties))
    return found


def test_the_collector_has_includes_clauses_to_check():
    """A parser that silently matches nothing would pass for ever."""
    clauses = includes_clauses()
    assert len(clauses) >= 3
    assert any("SensitivityLabelInfo" in props for _, props in clauses)


@pytest.mark.parametrize(
    "cmdlet,properties", includes_clauses(), ids=lambda v: str(v)[:40]
)
def test_every_included_property_exists_on_the_type(cmdlet, properties):
    """The check that `SharingCapability` would have failed.

    It is not a property of a site. `Get-PnPSite -Includes SharingCapability`
    is rejected outright, and the collector shipped with it because the name
    was plausible and nobody had read the type.

    Presence is necessary and not sufficient: a property the server does not
    project can be on the type and still be refused. That gap is recorded in
    the file rather than papered over here.
    """
    recorded = load(EXTERNAL / "pnp-powershell-3.3.0.json")
    key = RETURNS.get(cmdlet)
    assert key, f"{cmdlet} returns a type this recording does not cover"
    known = set(recorded["enums"][key]["values"])

    missing = [p for p in properties if p not in known]
    assert not missing, (
        f"{cmdlet} -Includes names {missing}, absent from the recorded "
        f"properties of {key.removesuffix('.properties')}. Either the name is "
        f"wrong or the recording is stale; read the assembly, do not guess."
    )
