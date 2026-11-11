"""No command that prepares a machine may open a session against a directory.

**WRITTEN BECAUSE THE RULE WAS BROKEN TWICE THE SAME WAY.** Permission to
install and declare the Microsoft Graph modules was read as permission to
authenticate, and a delegated session was opened against a directory nobody
had authorized. Documentation had already said not to; documentation is what
failed.

So the boundary is asserted here instead:

    prerequisites
        -> identity selected
        -> authentication requested
        -> authorization established for this operation
        -> acquisition

`Connect-MgGraph`, `Connect-PnPOnline`, `Connect-SPOService` and
`Connect-ExchangeOnline` are never side effects of preparing, checking, loading
a module, or describing what this engine can do. They belong to the commands a
person runs *in order to* reach a tenant, and to node others.

**THE PROOF IS RUNTIME AND IT CANNOT AUTHENTICATE.** `pwsh` is resolved from
PATH, so these tests put a stand-in on PATH that records every argument it is
given and refuses to do anything else. A command that tried to connect would be
recorded trying; it could not succeed, because the thing it would need is not
there. Nothing here reaches a network, and that is a property of the test
rather than a hope about it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

#: The four ways this engine can open a session. A collector that grows a
#: fifth adds it here, and the day it does is the day it must also decide
#: which commands may reach it.
AUTHENTICATIONS = (
    "Connect-MgGraph",
    "Connect-PnPOnline",
    "Connect-SPOService",
    "Connect-ExchangeOnline",
)

#: What a prerequisite check may legitimately ask PowerShell.
#:
#: A CLOSED LIST, AND THAT IS THE POINT. `doctor` and `setup` do invoke the
#: shell -- reading which modules a machine carries is exactly what a
#: prerequisite check is for -- so a gate saying "never touch PowerShell" would
#: be false, and one saying "never Connect" passes without measuring anything
#: on every other command. This says what these commands are allowed to want:
#: facts about this computer. Anything else is a new reach and fails here.
LOCAL_QUESTIONS = (
    "Get-Module -ListAvailable",
    "$PSVersionTable",
)

#: The commands whose PURPOSE is to reach a directory.
#:
#: Named, deliberately and shortly. Everything not here is preparation and is
#: held to the boundary below; a command that reaches a tenant and is not
#: listed fails, and so does a command listed here that nobody needed.
REACH_A_TENANT = frozenset(
    {"collect", "connect", "run", "migration-read", "login", "logout"}
)

#: How each preparing command is exercised.
#:
#: THE COMMANDS ARE NOT LISTED HERE -- they are read from the CLI's own parser,
#: which is the point. A hand-written list tests the operations somebody
#: remembered, and the incident this file exists about was a path nobody was
#: thinking about. A NEW COMMAND THEREFORE FAILS BY DEFAULT until it is
#: classified: either it reaches a tenant on purpose, or it is preparation and
#: is held to the boundary.
#:
#: This maps a command to the arguments that make it run at all. A command
#: missing from it still fails -- it is not skipped.
HOW_TO_RUN = {
    "doctor": [],
    "setup": [],
    "capabilities": ["--format", "json"],
    "list-rules": [],
    "show-rule": ["SPO-LIST-001"],
    "validate": [],
    "contracts": [],
    "stats": ["--help"],
    "explain": ["--help"],
    "evaluate": ["--help"],
    "assess": ["--help"],
    "verify": ["--help"],
    "report": ["--help"],
    "diff": ["--help"],
    # Relates evidence already on disk; it has no way to reach a directory.
    "inspect": ["--help"],
    "migration-verify": ["--help"],
    # The local record of connections. Reading, choosing and listing reach no
    # tenant; `connection remove` is `logout` by another name and is exercised
    # there.
    "status": [],
    "connection": ["list"],
    # A group named on its own says what it holds and reaches nothing. Its
    # complete paths are the flat commands above and below, by another name.
    "spo": [],
    "entra": [],
    "exo": [],
    "evidence": [],
    "governance": [],
    "rule": [],
    "migration": [],
    "engine": [],
}


def preparing_commands():
    """Every command this CLI has, minus the ones that exist to reach a tenant.

    Read from the parser rather than from a list somebody maintains. A command
    added tomorrow arrives here on its own, and arrives unclassified, which
    fails -- which is the only way this file keeps being true.
    """
    import argparse

    import m365_governance.cli as cli

    parser = cli._build_parser()
    action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    every = set(action.choices)
    return sorted(every - REACH_A_TENANT), sorted(every)


PREPARING = preparing_commands()[0]


@pytest.fixture
def pwsh_that_refuses(tmp_path):
    """A `pwsh` that answers nothing and writes down everything it was asked.

    Deliberately not a mock inside the process: the engine spawns a child, and
    a test that patched a Python function would prove something about the test
    rather than about the program. This is on PATH, which is where the real
    one is found.
    """
    log = tmp_path / "asked.jsonl"
    stand_in = tmp_path / "pwsh"
    stand_in.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        # It answers nothing and fails. A stand-in that returned plausible
        # output would let a command carry on as though a tenant had replied.
        "sys.stderr.write('this pwsh does not authenticate\\n')\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    stand_in.chmod(0o755)

    environment = dict(os.environ)
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment.get('PATH', '')}"
    # No project file is inherited: discovery walks upwards from the working
    # directory, and a developer's own tenant sitting above the checkout is
    # exactly the accident this file exists about.
    environment.pop("PH7X_ENGINE", None)
    return environment, log


def _asked(log: Path) -> list[str]:
    if not log.exists():
        return []
    return [linha for linha in log.read_text(encoding="utf-8").splitlines() if linha]


@pytest.mark.parametrize("command", PREPARING)
def test_preparing_only_asks_about_this_machine(command, pwsh_that_refuses, tmp_path):
    """Preparing the means is not permission to act.

    **THE FIRST VERSION OF THIS ASSERTED NOTHING.** It checked that node
    `Connect-` was requested, and most of these commands request node PowerShell
    at all, so it passed without measuring anything -- the shape this
    repository spends its effort removing, written into the gate against it.

    The second version overcorrected and claimed these commands never invoke
    PowerShell. `doctor` and `setup` do, and are right to: reading which
    modules are installed IS the prerequisite check.

    So what is asserted is the boundary that actually exists. Preparing may ask
    this machine what it carries. It may not ask a directory anything.
    """
    environment, log = pwsh_that_refuses

    assert command in HOW_TO_RUN, (
        f"`{command}` is a command nobody has classified. Either it exists to "
        "reach a directory, in which case add it to REACH_A_TENANT, or it is "
        "preparation, in which case say how to run it in HOW_TO_RUN so this "
        "boundary is checked on it. A new command is not exempt by being new."
    )

    subprocess.run(
        [sys.executable, "-m", "m365_governance.cli", command, *HOW_TO_RUN[command]],
        capture_output=True,
        text=True,
        env=environment,
        cwd=tmp_path,  # away from any project file in this checkout
        timeout=120,
    )

    asked = _asked(log)

    connecting = [p for p in asked if any(c in p for c in AUTHENTICATIONS)]
    assert not connecting, (
        f"`{command}` asked PowerShell to open a session against a "
        f"directory: {connecting}. That is how an unauthorized session was "
        "opened against an active tenant."
    )

    # AND WHAT IT *DID* ASK FOR IS INSPECTION, NOT ACTION.
    #
    # `doctor` and `setup` do run PowerShell, and should: reading which modules
    # are installed is the whole of what a prerequisite check is. So the
    # assertion is not that they stay away from the shell -- it is that
    # everything they ask it belongs to a closed list of questions about this
    # machine. A new kind of call fails here, which makes reaching further a
    # decision somebody takes rather than a line somebody adds.
    outside = [p for p in asked if not any(q in p for q in LOCAL_QUESTIONS)]
    assert not outside, (
        f"`{command}` asked PowerShell something that is not a "
        f"question about this machine: {outside[:2]}. Preparing may read what is "
        "installed here and nothing else. If this call is deliberate, add it "
        "to LOCAL_QUESTIONS and say what it establishes."
    )


def test_every_command_is_classified():
    """No command is exempt from this boundary by being forgotten.

    The pair of lists must cover the CLI exactly. A command that reaches a
    tenant is named; everything else is preparation and is exercised. Neither
    list may name something the CLI does not have, because a rule about a
    command nobody can run protects nothing.
    """
    preparing, every = preparing_commands()

    invented = REACH_A_TENANT - set(every)
    assert not invented, (
        f"REACH_A_TENANT names commands the CLI does not have: {invented}"
    )

    unclassified = set(preparing) - set(HOW_TO_RUN)
    assert not unclassified, (
        f"unclassified commands: {sorted(unclassified)}. Each either reaches a "
        "directory on purpose (REACH_A_TENANT) or is preparation and must be "
        "held to the boundary (HOW_TO_RUN)."
    )


def test_the_stand_in_would_catch_a_connection(pwsh_that_refuses, tmp_path):
    """That the test above can fail.

    A GATE THAT CANNOT FAIL IS A GATE THAT PROVES NOTHING, and this file's
    whole value is that it would have caught the incident. So the stand-in is
    made to record a real connection attempt, deliberately.
    """
    environment, log = pwsh_that_refuses

    subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "Connect-MgGraph -Scopes X"],
        capture_output=True,
        text=True,
        env=environment,
        cwd=tmp_path,
        timeout=60,
    )

    asked = _asked(log)
    assert any("Connect-MgGraph" in p for p in asked), (
        "the stand-in did not record a connection it was asked for, so the "
        "assertions above would pass whatever the engine did"
    )


def test_doctor_cannot_reach_a_session():
    """And statically: the installation check cannot reach a session at all.

    The runtime proof above says `doctor` did not connect on this run. This
    says it could not: nothing it imports is able to.
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "src" / "m365_governance"
    tree = ast.parse((root / "doctor.py").read_text(encoding="utf-8"))
    imported = {
        node.module.split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        a.name.split(".")[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for a in node.names
    }

    can_authenticate = {"connecting", "graph_token", "graph_slice"}
    assert not (imported & can_authenticate), (
        f"doctor.py imports {imported & can_authenticate}, which can open a "
        "session. An installation check must not be able to reach a tenant."
    )
