"""The command reference is derived, complete and current."""

import json
import pathlib
import subprocess
import sys

from m365_governance import collecting, grouping, reference, scenarios

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_every_grouped_path_has_an_entry_and_nothing_else_does():
    built = {entry["command"] for entry in reference.build()["commands"]}
    expected = set()
    for group in grouping.GROUPS:
        for path, flat in group.paths.items():
            if flat == ("inspect",):
                expected |= {
                    f"m365g {group.name} inspect {name}" for name in scenarios.SCENARIOS
                }
            else:
                expected.add(f"m365g {group.name} {' '.join(path)}")
    assert built == expected


def test_a_collection_entry_says_what_the_collector_says():
    entries = {e["command"]: e for e in reference.build()["commands"]}
    hubs = entries["m365g spo hub list"]
    assert hubs["reads"] == list(collecting.SLICES["hubs"].reads)
    assert hubs["kind"] == "enumeration" and hubs["needs"] == ["--tenant-url"]
    assert hubs["earlier_name"] == "m365g collect hubs"
    sharing = entries["m365g spo sharing list"]
    assert "SPO-SHARE-001" in sharing["feeds_rules"]
    # A permission nobody established is published as that, never as none.
    assert all(e.get("permissions", ["x"]) for e in entries.values())


def test_a_scenario_entry_says_it_reaches_no_tenant():
    entries = {e["command"]: e for e in reference.build()["commands"]}
    scenario = entries["m365g governance inspect external-access"]
    assert scenario["reaches_a_tenant"] is False
    assert scenario["reads_collections"] == [
        "sites-sharing",
        "tenant-sharing",
        "guests",
    ]


def test_the_written_reference_is_current():
    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "command-reference.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout
    written = json.loads((ROOT / "docs" / "COMMAND-REFERENCE.json").read_text())
    assert written == reference.build()
