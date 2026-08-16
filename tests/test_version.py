"""One version, read rather than written down twice.

`__version__` used to be a literal in `m365_governance/__init__.py`, beside the
one in `pyproject.toml`. Releasing 1.0.0b2 bumped the packaging version and
left the literal at 1.0.0b1: the wheel was named for one version and the
program answered with another.

The naming half is cosmetic. The other half is not. This value travels into
every assessment as `engine_version`, so an assessment produced by one build
stated that a different build had decided it. In an engine whose whole claim is
that a conclusion can be traced back to what produced it, a version that lies
is not a typo.

Nothing caught it. The publish workflow compares the built filename to the
release tag, which agreed; the drift was between the filename and the running
program, and no gate looked there.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

from m365_governance import __version__

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _versao_declarada() -> str:
    """A versão em pyproject.toml, lida sem um analisador de TOML.

    Deliberadamente literal: este teste existe para comparar duas fontes, e
    lê-las as duas pela mesma biblioteca poria as duas de acordo por
    construção.
    """
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.M)
    assert m, "pyproject.toml não declara version"
    return m.group(1)


def test_a_versao_do_programa_e_a_versao_empacotada():
    declarada = _versao_declarada()
    assert __version__ == declarada, (
        f"o pacote declara {declarada!r} e o programa responde {__version__!r}. "
        f"Esta é a versão que vai para `engine_version` de cada assessment: "
        f"divergirem faz um documento afirmar que outra build o decidiu."
    )


def test_a_linha_de_comandos_responde_a_mesma_versao():
    """Pela mesma via que um utilizador usa, e não pela importação."""
    r = subprocess.run(
        [sys.executable, "-m", "m365_governance.cli", "--version"],
        capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == _versao_declarada(), (
        f"`--version` respondeu {r.stdout.strip()!r} e o pacote declara "
        f"{_versao_declarada()!r}")


def test_a_versao_nao_e_a_de_um_pacote_nao_instalado():
    """A alternativa quando não há distribuição a que perguntar não pode
    passar por uma versão real: um `0.0.0+unknown` num relatório é uma
    admissão, e é isso que deve ser."""
    if __version__ == "0.0.0+unknown":
        pytest.fail(
            "o pacote não está instalado, por isso `__version__` é a "
            "alternativa. Corra `pip install -e .` antes da suíte: um "
            "assessment produzido assim não diz que motor o decidiu.")
