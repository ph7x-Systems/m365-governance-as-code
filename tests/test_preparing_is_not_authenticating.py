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
person runs *in order to* reach a tenant, and to no others.

**THE PROOF IS RUNTIME AND IT CANNOT AUTHENTICATE.** `pwsh` is resolved from
PATH, so these tests put a stand-in on PATH that records every argument it is
given and refuses to do anything else. A command that tried to connect would be
recorded trying; it could not succeed, because the thing it would need is not
there. Nothing here reaches a network, and that is a property of the test
rather than a hope about it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

#: The four ways this engine can open a session. A collector that grows a
#: fifth adds it here, and the day it does is the day it must also decide
#: which commands may reach it.
AUTENTICACOES = (
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
INSPECCOES = (
    "Get-Module -ListAvailable",
    "$PSVersionTable",
)

#: Commands that must not authenticate under any arguments.
#:
#: THIS IS THE LIST THE INCIDENTS WERE ABOUT. Every one of them is something
#: somebody runs while finding out whether this tool works at all -- before
#: deciding whether to point it at anything of theirs.
PREPARAM = (
    ["doctor"],
    ["setup"],
    ["capabilities", "--format", "json"],
    ["list-rules"],
    ["validate"],
    ["contracts"],
    ["stats", "--help"],
    ["connect", "--dry-run", "--client-id", "00000000-0000-0000-0000-000000000001",
     "--tenant-url", "https://example-admin.sharepoint.com"],
)


@pytest.fixture
def pwsh_que_recusa(tmp_path):
    """A `pwsh` that answers nothing and writes down everything it was asked.

    Deliberately not a mock inside the process: the engine spawns a child, and
    a test that patched a Python function would prove something about the test
    rather than about the program. This is on PATH, which is where the real
    one is found.
    """
    registo = tmp_path / "pedido.jsonl"
    falso = tmp_path / "pwsh"
    falso.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(registo)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        # It answers nothing and fails. A stand-in that returned plausible
        # output would let a command carry on as though a tenant had replied.
        "sys.stderr.write('this pwsh does not authenticate\\n')\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    falso.chmod(0o755)

    ambiente = dict(os.environ)
    ambiente["PATH"] = f"{tmp_path}{os.pathsep}{ambiente.get('PATH', '')}"
    # No project file is inherited: discovery walks upwards from the working
    # directory, and a developer's own tenant sitting above the checkout is
    # exactly the accident this file exists about.
    ambiente.pop("PH7X_ENGINE", None)
    return ambiente, registo


def _pedidos(registo: Path) -> list[str]:
    if not registo.exists():
        return []
    return [linha for linha in registo.read_text(encoding="utf-8").splitlines() if linha]


@pytest.mark.parametrize("comando", PREPARAM, ids=lambda c: c[0])
def test_preparar_so_pergunta_por_esta_maquina(comando, pwsh_que_recusa, tmp_path):
    """Preparing the means is not permission to act.

    **THE FIRST VERSION OF THIS ASSERTED NOTHING.** It checked that no
    `Connect-` was requested, and most of these commands request no PowerShell
    at all, so it passed without measuring anything -- the shape this
    repository spends its effort removing, written into the gate against it.

    The second version overcorrected and claimed these commands never invoke
    PowerShell. `doctor` and `setup` do, and are right to: reading which
    modules are installed IS the prerequisite check.

    So what is asserted is the boundary that actually exists. Preparing may ask
    this machine what it carries. It may not ask a directory anything.
    """
    ambiente, registo = pwsh_que_recusa

    subprocess.run(
        [sys.executable, "-m", "m365_governance.cli", *comando],
        capture_output=True, text=True, env=ambiente,
        cwd=tmp_path,  # away from any project file in this checkout
        timeout=120,
    )

    pedidos = _pedidos(registo)

    culpados = [p for p in pedidos if any(c in p for c in AUTENTICACOES)]
    assert not culpados, (
        f"`{' '.join(comando)}` asked PowerShell to open a session against a "
        f"directory: {culpados}. That is how an unauthorized session was "
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
    fora = [p for p in pedidos if not any(q in p for q in INSPECCOES)]
    assert not fora, (
        f"`{' '.join(comando)}` asked PowerShell something that is not a "
        f"question about this machine: {fora[:2]}. Preparing may read what is "
        "installed here and nothing else. If this call is deliberate, add it "
        "to INSPECCOES and say what it establishes."
    )


def test_o_duplo_apanharia_uma_autenticacao(pwsh_que_recusa, tmp_path):
    """That the test above can fail.

    A GATE THAT CANNOT FAIL IS A GATE THAT PROVES NOTHING, and this file's
    whole value is that it would have caught the incident. So the stand-in is
    made to record a real connection attempt, deliberately.
    """
    ambiente, registo = pwsh_que_recusa

    subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "Connect-MgGraph -Scopes X"],
        capture_output=True, text=True, env=ambiente, cwd=tmp_path, timeout=60,
    )

    pedidos = _pedidos(registo)
    assert any("Connect-MgGraph" in p for p in pedidos), (
        "the stand-in did not record a connection it was asked for, so the "
        "assertions above would pass whatever the engine did"
    )


def test_o_doctor_nao_importa_o_que_autentica():
    """And statically: the installation check cannot reach a session at all.

    The runtime proof above says `doctor` did not connect on this run. This
    says it could not: nothing it imports is able to.
    """
    import ast

    raiz = Path(__file__).resolve().parents[1] / "src" / "m365_governance"
    arvore = ast.parse((raiz / "doctor.py").read_text(encoding="utf-8"))
    importados = {
        no.module.split(".")[-1]
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom) and no.module
    } | {
        a.name.split(".")[-1]
        for no in ast.walk(arvore) if isinstance(no, ast.Import) for a in no.names
    }

    autenticam = {"connecting", "graph_token", "graph_slice"}
    assert not (importados & autenticam), (
        f"doctor.py imports {importados & autenticam}, which can open a "
        "session. An installation check must not be able to reach a tenant."
    )
