"""What we distribute is what we tested, and the list stopped being a list.

THE DEFECT, THREE TIMES, IN THE SAME SHAPE.

    collectors/**/*.ps1   shipped a collector that could not import one of its
                          own .psm1 modules
    five directories      counted in the wheel gate, so data/live-proof.json
                          never entered a wheel at all
    six refresh scripts   three of them wired into the site's gate

Each was a POSITIVE ENUMERATION OF AN OPEN SET: a list somebody had to
remember to extend, at the moment they were thinking about something else. The
entries were not the problem. The shape was.

The third one cost the most. `live-proof.json` is the register the proof ladder
is derived from -- the number this product is answerable for -- and an
installed engine raised `FileNotFoundError` from `m365-governance capabilities`
while every gate stayed green, because no gate ran that command against an
installed artefact and no gate compared the tree against the wheel for
anything but PowerShell.

So this file inverts it. It walks what is on disk, applies exclusions that each
carry a reason, and requires everything else to be product. A file added to
`data/` ships unless somebody writes down why it should not.
"""

from __future__ import annotations

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "m365_governance" / "data"

#: The only files under `data` that are not product, each with the reason.
#:
#: NOT A CONVENIENCE LIST. Adding a line here is declaring that a file the
#: product carries in its source tree must not reach the people who install it,
#: and that is a claim somebody should have to write a sentence for. "It is not
#: needed" is not a sentence: a file the runtime does not read today is a file
#: this gate should be told about, not one somebody quietly drops.
NOT_PRODUCT = {
    "__pycache__": (
        "this interpreter's own bytecode cache. It differs between machines, "
        "so a wheel carrying it is a wheel whose contents depend on who built "
        "it"
    ),
}


def _excluded(relative: pathlib.Path) -> str:
    for part in relative.parts:
        if part in NOT_PRODUCT:
            return part
    if relative.suffix == ".pyc":
        return "__pycache__"
    return ""


def test_every_file_under_data_is_declared_product_or_declared_not():
    """The set is walked, never recalled.

    A test that named the directories it expected would be the same list that
    has now been wrong three times, one layer further out.
    """
    for path in DATA.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(DATA)
        reason = _excluded(relative)
        if reason:
            assert NOT_PRODUCT[reason], (
                f"{relative} is excluded from the product by `{reason}` and "
                "nothing says why"
            )


def test_the_packaging_declaration_carries_the_whole_directory():
    """THE CHEAP HALF OF THE GATE, AND THE ONE THAT RUNS IN MILLISECONDS.

    Building a wheel proves this properly and belongs in `release-check`; this
    reads the declaration and fails the moment somebody narrows it back into a
    list of remembered directories. It is here because the expensive gate runs
    at release and this runs on every commit, and `live-proof.json` was
    introduced and forgotten between two releases.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["tool"]["setuptools"]["package-data"]["m365_governance.data"]

    assert declared == ["**/*"], (
        "the packaging declaration stopped being total. Whatever replaced it "
        "is a list of the directories somebody remembered, which is the shape "
        f"that has now failed three times: {declared}"
    )

    excluded = (
        pyproject["tool"]["setuptools"]
        .get("exclude-package-data", {})
        .get("m365_governance.data", [])
    )
    for pattern in excluded:
        stem = pattern.strip("*/").split("/")[0].lstrip("*.")
        assert stem in NOT_PRODUCT or stem == "pyc", (
            f"`{pattern}` is excluded from the wheel and this file does not "
            "say why. An exclusion nobody wrote a reason for is a file that "
            "silently stops shipping"
        )


def test_everything_the_runtime_reads_from_data_is_under_that_declaration():
    """WHAT THE RUNTIME ACTUALLY OPENS, found in the code rather than assumed.

    `live_proof.REGISTRY` and its neighbours are built from
    `Path(__file__).parent / "data" / ...`, and each one is a file that must
    exist beside an installed module or the command that reads it raises rather
    than degrades. This resolves them and checks they are on disk, so a
    reference to a file nobody shipped fails here instead of in somebody's
    terminal.
    """
    import importlib
    import pkgutil

    import m365_governance

    opened: list[tuple[str, pathlib.Path]] = []
    for info in pkgutil.iter_modules(m365_governance.__path__):
        module = importlib.import_module(f"m365_governance.{info.name}")
        for name in dir(module):
            value = getattr(module, name)
            if not isinstance(value, pathlib.Path):
                continue
            if DATA in value.parents or value.parent == DATA:
                opened.append((f"{info.name}.{name}", value))

    assert opened, (
        "no module was found holding a path into `data`, which means this test "
        "is checking nothing. It found `live_proof.REGISTRY` when it was "
        "written"
    )

    missing = [f"{who} -> {path}" for who, path in opened if not path.exists()]
    assert missing == [], (
        "the runtime holds a path to a file that is not in the source tree: "
        + ", ".join(missing)
    )
