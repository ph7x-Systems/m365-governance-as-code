"""The command surface that existed before the CLI was regrouped keeps working.

Written BEFORE anything moved (owner decision, 2026-11-11; docs/CLI.md). The
desktop product, the site's documentation and every script somebody already
has invoke this engine as a subprocess, by the names and options frozen in
`tests/frozen/cli-v1-surface.json`. A regrouped CLI adds names; it never takes
one of these away, never drops an option one of them took, and never narrows a
choice.

The file is a record of what was published, read from the parser on the day it
was frozen. It is not regenerated: a change that needs it edited is a change
that breaks somebody.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import m365_governance.cli as cli

FROZEN = json.loads(
    (Path(__file__).parent / "frozen" / "cli-v1-surface.json").read_text(
        encoding="utf-8"
    )
)["commands"]

#: How the desktop product invokes the engine today, read from its source
#: (EngineProcess callers). Each must still parse, word for word.
CONSUMER_INVOCATIONS = (
    ["connect", "--project", "p.toml", "--format", "json"],
    [
        "connect",
        "--client-id",
        "c",
        "--tenant-url",
        "https://t-admin.sharepoint.com",
        "--device-login",
        "--format",
        "json",
    ],
    ["collect", "sites", "--project", "p.toml", "--output", "evidence"],
    [
        "collect",
        "owners",
        "--client-id",
        "c",
        "--site-url",
        "https://t.sharepoint.com/sites/a",
        "--output",
        "evidence",
        "--device-login",
    ],
    [
        "run",
        "--project",
        "p.toml",
        "--output",
        "evidence",
        "--format",
        "json",
        "--out",
        "report.json",
        "--bundle",
        "runs",
        "--fail-on",
        "nothing",
    ],
    ["run", "--project", "p.toml", "--profile", "profile.yaml", "--device-login"],
    ["verify", "assessment.json"],
    ["report", "run.json", "--format", "html"],
    ["diff", "before.json", "after.json", "--format", "json"],
    ["capabilities", "--format", "json"],
    ["contracts", "--out", "bundle"],
)


def _commands() -> dict[str, argparse.ArgumentParser]:
    parser = cli._build_parser()
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return dict(action.choices)


def test_there_are_nineteen_frozen_commands():
    assert len(FROZEN) == 19


@pytest.mark.parametrize("name", sorted(FROZEN))
def test_a_frozen_command_still_exists_with_everything_it_took(name):
    commands = _commands()
    assert name in commands, f"`{name}` was published and is gone"
    sub = commands[name]
    options = {o for a in sub._actions for o in a.option_strings}
    missing = set(FROZEN[name]["options"]) - options
    assert not missing, f"`{name}` no longer takes {sorted(missing)}"
    positionals = [a.dest for a in sub._actions if not a.option_strings]
    assert (
        positionals[: len(FROZEN[name]["positionals"])] == FROZEN[name]["positionals"]
    )
    for dest, values in FROZEN[name]["choices"].items():
        now = next(a for a in sub._actions if a.dest == dest and a.option_strings)
        assert set(values) <= {str(c) for c in now.choices}, (
            f"`{name} --{dest}` lost a value"
        )


@pytest.mark.parametrize("argv", CONSUMER_INVOCATIONS, ids=lambda a: " ".join(a[:2]))
def test_a_consumer_invocation_still_parses(argv):
    args = cli._build_parser().parse_args(argv)
    assert args.command == argv[0]


def test_both_executable_names_are_still_published():
    text = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'm365g = "m365_governance.cli:main"' in text
    assert 'm365-governance = "m365_governance.cli:main"' in text


def test_a_refusal_is_still_exit_two(tmp_path, capsys, monkeypatch):
    """Exit 2 is a refusal and 1 a negative result (docs/FIRST-RUN-CONTRACT.md)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("M365G_HOME", str(tmp_path / "home"))
    assert cli.main(["collect", "sites", "--output", str(tmp_path / "e")]) == 2
    assert "refusing to run" in capsys.readouterr().err
