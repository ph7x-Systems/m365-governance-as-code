"""A grouped command is the flat command by another name, and never a new one.

docs/CLI.md states it; grouping.py owns the table. These tests hold the table
to the parser and to the collector's registry in both directions, so a
collection nobody gave a path fails, and so does a path to something this
engine does not have.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import m365_governance.cli as cli
from m365_governance import collecting, grouping

FROZEN = json.loads(
    (Path(__file__).parent / "frozen" / "cli-v1-surface.json").read_text(
        encoding="utf-8"
    )
)["commands"]

#: Flat commands that are not under a group, on purpose: signing in and asking
#: the tenant are what a person does before choosing a service.
UNGROUPED = {"connect"}

PATHS = [
    (group, path, flat)
    for group in grouping.GROUPS
    for path, flat in group.paths.items()
]


def _flat_commands() -> set[str]:
    parser = cli._build_parser()
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return set(action.choices) - set(grouping.BY_NAME)


def test_every_collection_has_exactly_one_grouped_path():
    reached = [
        flat[1] for _, _, flat in PATHS if flat[0] == "collect" and len(flat) == 2
    ]
    assert sorted(reached) == sorted(collecting.SLICES), (
        "a collection has no grouped path, or two, or a path names one that "
        "does not exist"
    )


def test_every_path_leads_to_a_command_this_engine_has():
    flat = _flat_commands()
    for group, path, target in PATHS:
        assert target[0] in flat, f"{group.name} {' '.join(path)} -> {target[0]}"


def test_every_published_command_is_reachable_by_a_grouped_path():
    reached = {target[0] for _, _, target in PATHS}
    assert set(FROZEN) - reached == UNGROUPED


def test_no_group_takes_the_name_of_a_command():
    assert not set(grouping.BY_NAME) & (
        set(FROZEN) | {"login", "status", "logout", "connection"}
    )


@pytest.mark.parametrize(
    ("grouped", "flat"),
    [
        (["rule", "list"], ["list-rules"]),
        (["rule", "show", "SPO-LIST-001"], ["show-rule", "SPO-LIST-001"]),
        (["rule", "get", "SPO-LIST-001"], ["show-rule", "SPO-LIST-001"]),
        (
            ["engine", "capabilities", "--format", "json"],
            ["capabilities", "--format", "json"],
        ),
        (["governance", "verify", "a.json"], ["verify", "a.json"]),
        (["migration", "verify", "a", "b"], ["migration-verify", "a", "b"]),
        (
            [
                "spo",
                "site",
                "list",
                "--tenant-url",
                "https://t-admin.sharepoint.com",
                "--output",
                "e",
            ],
            [
                "collect",
                "sites",
                "--tenant-url",
                "https://t-admin.sharepoint.com",
                "--output",
                "e",
            ],
        ),
        (
            ["spo", "tenant", "sharing", "get", "--output", "e"],
            ["collect", "tenant-sharing", "--output", "e"],
        ),
        (
            ["entra", "ca", "list", "--output", "e"],
            ["collect", "conditional-access", "--output", "e"],
        ),
        (
            ["evidence", "collect", "owners", "--output", "e"],
            ["collect", "owners", "--output", "e"],
        ),
    ],
    ids=lambda v: " ".join(v[:4]),
)
def test_a_grouped_command_parses_to_exactly_the_flat_one(grouped, flat):
    parser = cli._build_parser()
    assert grouping.regroup(grouped) == flat
    assert vars(parser.parse_args(grouping.regroup(grouped))) == vars(
        parser.parse_args(flat)
    )


def test_what_is_not_a_complete_path_is_left_for_the_parser():
    for argv in (
        [],
        ["collect", "sites"],
        ["spo"],
        ["spo", "--help"],
        ["spo", "site"],
        ["rule", "nope"],
    ):
        assert grouping.regroup(argv) == argv


def test_a_grouped_command_runs_and_says_what_the_flat_one_says(capsys):
    assert cli.main(["rule", "list"]) == 0
    grouped = capsys.readouterr().out
    assert cli.main(["list-rules"]) == 0
    assert grouped == capsys.readouterr().out and "SPO-LIST-001" in grouped


@pytest.mark.parametrize("group", grouping.GROUPS, ids=lambda g: g.name)
def test_a_group_on_its_own_lists_what_it_holds(group, capsys):
    for argv in ([group.name], [group.name, "--help"]):
        assert cli.main(argv) == 0
        out = capsys.readouterr().out
        for path in group.paths:
            assert f"m365g {group.name} {' '.join(path)}" in out
    assert "keeps working" in out


def test_a_path_a_group_does_not_hold_is_a_refusal_that_shows_the_group(capsys):
    assert cli.main(["spo", "nope"]) == 2
    err = capsys.readouterr().err
    assert "m365g spo has no `nope`" in err and "m365g spo site list" in err


def test_the_top_level_help_names_the_groups(capsys):
    with pytest.raises(SystemExit) as stop:
        cli.main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for group in grouping.GROUPS:
        assert group.name in out


# --- help: where to start, what a read needs, and why something failed ---------


def test_the_overview_says_where_to_start_and_what_a_view_is(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    needed = ["Start here", "m365g login", "m365g status", "Session"]
    needed += ["--evidence-out", "--output text|json|csv|md", "still work"]
    for words in needed:
        assert words in out, words
    assert "list-rules           " not in out, "the flat listing is printed twice"


@pytest.mark.parametrize(
    ("group", "path", "flat"),
    [p for p in PATHS if p[2][0] == "collect" and len(p[2]) == 2],
    ids=lambda v: v.name if isinstance(v, grouping.Group) else " ".join(v),
)
def test_every_read_says_what_it_reads_needs_and_feeds(group, path, flat, capsys):
    assert cli.main([group.name, *path, "--help"]) == 0
    out = capsys.readouterr().out
    for label in (
        "Reads",
        "Permissions",
        "Needs",
        "Signs in",
        "Feeds rules",
        "Examples",
    ):
        assert label in out, label
    assert collecting.SLICES[flat[1]].describes in out
    assert f"m365g collect {flat[1]} --help" in out


def test_a_read_a_session_does_not_cover_says_so_in_its_help(capsys):
    cli.main(["exo", "forwarding", "get", "--help"])
    assert "a kept session is not reused" in capsys.readouterr().out
    cli.main(["spo", "site", "list", "--help"])
    assert "active connection" in capsys.readouterr().out
    cli.main(["entra", "ca", "list", "-h"])
    assert "never prompts" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        (
            "AADSTS65001: The user or administrator has not consented",
            "consent",
        ),
        (
            "Access denied. You do not have permission to perform this action.",
            "authorization, not authentication",
        ),
        ("something this engine has never seen", "the collector's last words"),
    ],
    ids=["consent", "denied", "unrecognised"],
)
def test_a_failed_collection_says_why_where_it_can_tell(said, expected, capsys):
    from types import SimpleNamespace

    cli._explain_failure(SimpleNamespace(stderr=said, stdout=""))
    assert expected in capsys.readouterr().err
