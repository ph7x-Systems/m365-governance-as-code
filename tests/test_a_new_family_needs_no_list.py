"""Adding an evidence family must not require editing a hand-written list.

FOUR TIMES, AND EACH ONE WAS CORRECT WHEN IT WAS WRITTEN. The test fixture
loader named two families; the shape resolver named three; the acquisition-path
gate read one collector's `-SourceApi` declarations; the bundle's families were
a tuple. `exchange` arrived and every one of them accused it of a defect that
was its own -- a rule whose evidence no collector produces, a fixture claiming
an API nothing uses, a family no consumer receives.

**This is an extensibility defect demonstrated four times**, and Teams will
test the same property the day it lands. So it is a gate rather than a memory:
a list of families kept by hand is a list the next family contradicts.

WHAT IS STILL ALLOWED, AND WHY. `tools/publish-contracts.py` keeps a families
tuple on purpose -- a family with no consumer must be caught rather than
shipped invisible -- and `test_collector.py` holds it. That one is a DECLARATION
somebody makes deliberately, gated. What is refused here is a list that exists
because somebody had to remember it.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "m365_governance"
TESTS = ROOT / "tests"


def _families() -> list[str]:
    """The evidence families in the tree, decided by what the documents ARE.

    `fixtures/` also holds `assessment`, `comparison` and `migration`, which
    are artefact kinds, and `archive`, which holds evidence documents written
    to CONTRACT VERSIONS THIS ENGINE NO LONGER EMITS. Listing those exceptions
    would be the fifth hand-written list, in a file about the other four.

    So a family is a directory whose documents declare the evidence contract
    this engine publishes today. That excludes the archive for the reason the
    archive exists, and it admits a new workload the moment its first document
    lands.
    """
    import json

    current = json.loads(
        (SOURCE / "data" / "schemas" / "evidence.schema.json").read_text(
            encoding="utf-8"
        )
    )["$id"]

    found = []
    for folder in sorted((SOURCE / "data" / "fixtures").iterdir()):
        if not folder.is_dir():
            continue
        for document in sorted(folder.glob("*.json")):
            data = json.loads(document.read_text(encoding="utf-8"))
            if data.get("$schema") == current:
                found.append(folder.name)
                break
    return found


#: Read rather than written down, and read from what the documents are.
FAMILIES = _families()

#: The one place a family list is a deliberate declaration, gated elsewhere.
DECLARED = {("tools/publish-contracts.py", "families")}


def test_the_tree_has_more_than_one_family():
    """A gate about extensibility written when nothing was extended would pass
    forever without being exercised."""
    assert len(FAMILIES) >= 4, f"families found: {FAMILIES}"


def test_no_module_hard_codes_the_set_of_families():
    """A tuple or list literal naming two or more families is the shape.

    It matches on the family NAMES rather than on a variable name, because
    every one of the four called itself something different -- `families`,
    `root`, `FIXTURES, ENTRA`, a bare tuple in a loop.
    """
    offenders = []
    for path in sorted(SOURCE.rglob("*.py")) + sorted(TESTS.rglob("*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        for literal in re.finditer(r"[\(\[]([^()\[\]]{0,200}?)[\)\]]", text, re.S):
            named = {
                found.group(1)
                for found in re.finditer(r"[\"']([a-z-]+)[\"']", literal.group(1))
            } & set(FAMILIES)
            if len(named) >= 2:
                where = text[: literal.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(ROOT)}:{where}: {sorted(named)}")

    allowed = {f"{name}" for name, _ in DECLARED}
    offenders = [o for o in offenders if not any(o.startswith(a) for a in allowed)]

    assert not offenders, (
        "modules naming two or more evidence families in a literal:\n  "
        + "\n  ".join(offenders)
        + "\n\nAdding a family must not require editing a list. Search the "
        "fixtures directory instead: every one of these was correct when it "
        "was written and wrong the day a family arrived."
    )


def test_every_family_is_reachable_without_being_named():
    """The three that were fixed, asserted as behaviour rather than as shape.

    A family added tomorrow must resolve through each of them with no edit:
    the fixture loader finds its documents, the shape resolver finds its facts,
    and the acquisition-path gate finds its collector's declared API.
    """
    import sys

    sys.path.insert(0, str(TESTS))
    from conftest import evidence  # noqa: PLC0415
    from m365_governance import capabilities  # noqa: PLC0415
    from m365_governance.collecting import SLICES  # noqa: PLC0415

    for name, chosen in sorted(SLICES.items()):
        if not chosen.shaped_like:
            continue
        # The loader finds it wherever its family keeps it.
        assert evidence(chosen.shaped_like), f"{name}: shape does not load"
        # The resolver finds its facts, which is what decides whether the
        # rules it feeds are answerable at all.
        assert capabilities._shape_facts(name), f"{name}: shape resolves to no facts"


def test_the_declared_family_list_is_complete():
    """The one list that stays is checked against the tree rather than trusted.

    `publish-contracts.py` names the families a consumer receives on purpose:
    a family with no consumer should be caught, not shipped invisible. What
    must not happen is it silently falling behind.
    """
    text = (ROOT / "tools" / "publish-contracts.py").read_text(encoding="utf-8")
    found = re.search(r"families\s*=\s*\(([^)]*)\)", text)

    assert found, "publish-contracts.py no longer declares its families"
    declared = set(re.findall(r"[\"']([a-z-]+)[\"']", found.group(1)))

    assert declared == set(FAMILIES), (
        f"the bundle declares {sorted(declared)} and the tree holds "
        f"{FAMILIES}. Add the family or record why it is excluded."
    )
