"""The queue cannot be called exhausted while a card is unenumerated.

Rule 8 of the charter's continuation procedure as a gate rather than as advice.
It was advice for one day, during which the claim was made twice — and the day
after, a card was reported as needing a Windows machine when what it needed was
a CI job nobody had looked for.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "queue-claim-check.py")


def _gate():
    spec = importlib.util.spec_from_file_location("queue_claim_check", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _gate()

CLAIMED = """# Queue

## THING-001 — a card

**authority:** repository · **next action:** write the thing

Prose about the thing.

### OTHER-002 — another

**authority:** owner · **next action:** a decision
"""


def test_a_heading_without_an_identifier_is_a_section_and_not_a_card():
    """The queue groups cards under prose, and prose is not a unit of work."""
    text = "## Where to start\n\nSome prose.\n" + CLAIMED

    assert [name for name, _line, _body in gate.cards(text)] == [
        "THING-001",
        "OTHER-002",
    ]


def test_a_claimed_queue_passes(tmp_path, monkeypatch, capsys):
    queue = tmp_path / "NEXT-SLICE.md"
    queue.write_text(CLAIMED, encoding="utf-8")
    monkeypatch.setattr(gate, "QUEUE", str(queue))

    assert gate.main() == 0
    assert "2 cards, all claimed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "body,missing",
    [
        ("**authority:** repository\n", "next action"),
        ("**next action:** something\n", "authority"),
    ],
    ids=["no next action", "no authority"],
)
def test_a_card_missing_either_field_refuses(
    tmp_path, monkeypatch, capsys, body, missing
):
    queue = tmp_path / "NEXT-SLICE.md"
    queue.write_text(f"## THING-001 — a card\n\n{body}", encoding="utf-8")
    monkeypatch.setattr(gate, "QUEUE", str(queue))

    assert gate.main() == 1
    assert missing in capsys.readouterr().err


def test_an_authority_nobody_recognises_refuses(tmp_path, monkeypatch, capsys):
    """Four authorities, because they are four different waits. `soon` is not
    one of them, and neither is `me`."""
    queue = tmp_path / "NEXT-SLICE.md"
    queue.write_text(
        "## THING-001 — a card\n\n**authority:** soon · **next action:** x\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "QUEUE", str(queue))

    assert gate.main() == 1
    assert "is not one of" in capsys.readouterr().err


def test_a_queue_with_no_cards_refuses(tmp_path, monkeypatch):
    """A check that finds nothing passes forever."""
    queue = tmp_path / "NEXT-SLICE.md"
    queue.write_text("# Queue\n\nNothing here.\n", encoding="utf-8")
    monkeypatch.setattr(gate, "QUEUE", str(queue))

    with pytest.raises(gate.Unclaimed):
        gate.main()


def test_the_real_queue_is_claimed(capsys):
    """The property that matters, on the file it matters for."""
    assert gate.main() == 0

    said = capsys.readouterr().out
    assert "need no external authority" in said, (
        "every card in the queue names an external authority. That is a queue "
        "somebody should read again before saying there is nothing to do."
    )
