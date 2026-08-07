"""Where the product's content comes from, and what a report says about it.

**A clean installation is the reference environment. The development
repository is a convenience, not the execution model.**

None of these tests can prove that. Only the clean-install job in CI can:
everything here runs from the repository root, which is exactly the condition
under which the whole suite once agreed that a product with no packaged
content was working. What these tests do is hold the three decisions in place
so a later change has to argue with them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DATA
from m365_governance import resources
from m365_governance.resources import BUNDLED, Source, missing, packaged, resolve


def test_every_bundled_directory_is_present():
    """What the clean-install gate proves for an installed copy, asserted here
    for a source checkout: the five directories exist where the import system
    says the package is."""
    assert missing() == []
    for name in BUNDLED:
        assert packaged(name).is_dir()


def test_the_package_content_is_the_repository_content():
    """One copy, not two. A second tree at the repository root would drift,
    and the one the tests agreed with would be the one nobody installs."""
    assert packaged("rules").resolve() == (DATA / "rules").resolve()


def test_asking_for_something_that_is_not_bundled_is_an_error():
    with pytest.raises(KeyError):
        packaged("secrets")


# ---------------------------------------------------------------------------
# The three rules
# ---------------------------------------------------------------------------


def test_a_packaged_rule_changes_only_with_a_release():
    """Rule 1, expressed as the only thing a test can check about it: nothing
    outside the package is consulted when the caller supplies no path.

    The ceremony itself is the point. A rule is part of the observable
    behaviour of this product, so changing one changes what the product says.
    """
    source = resolve("rules", None)
    assert source.origin == "package"
    assert source.is_packaged
    assert source.path == packaged("rules")


def test_external_content_declares_itself(tmp_path):
    """Rule 2. A finding produced by rules nobody can identify is not
    reproducible, so the report says which it was."""
    external = resolve("rules", tmp_path / "my-rules")
    assert external.origin == "external"
    assert not external.is_packaged
    assert str(tmp_path) in external.describe()

    assert resolve("rules", None).describe() == "shipped with this version"


def test_an_override_replaces_and_never_merges(tmp_path):
    """Rule 3. Either the packaged set complete, or the supplied set complete.

    "Defaults plus a few of mine" produces a rule set that exists only in the
    memory of whoever typed the command, and two runs of the same version stop
    meaning the same thing.
    """
    mine = tmp_path / "my-rules"
    mine.mkdir()
    chosen = resolve("rules", mine)
    assert chosen.path == mine
    # Nothing packaged is reachable through the result. There is no second
    # path, no list, and no fallback: one directory, and it is the one asked
    # for.
    assert not hasattr(chosen, "paths")
    assert chosen.path != packaged("rules")


def test_the_rule_source_reaches_the_report(tmp_path):
    """The evidence for rule 2: it survives into the rendered report and back
    out of a stored one."""
    from conftest import evidence, rule
    from m365_governance.engine import evaluate
    from m365_governance.reporting import to_markdown
    from m365_governance.results import Run

    run = evaluate([rule("SPO-LIST-001")], evidence("list-over-limit"))
    run.rule_source = "shipped with this version"
    assert "- Rules: shipped with this version" in to_markdown(run)

    restored = Run.from_dict(run.to_dict())
    assert restored.rule_source == run.rule_source


# ---------------------------------------------------------------------------
# The defect this module exists to prevent
# ---------------------------------------------------------------------------


def test_no_module_resolves_content_from_its_own_position():
    """The defect, named so it cannot come back quietly.

    `Path(__file__).resolve().parents[2] / "collectors"` is right from
    `src/m365_governance/` and points at `lib/python3.x/collectors` from
    site-packages. It looks relocatable precisely because it avoided the
    obvious mistake of using the working directory.
    """
    import ast

    source = Path(resources.__file__).parent
    for module in sorted(source.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # `<anything>.parents[n]`, in code. Comments and docstrings are
            # not walked, which matters: two modules describe this defect in
            # prose precisely so it is not repeated, and a textual search
            # would fail on the explanation rather than on the mistake.
            if not isinstance(node, ast.Subscript):
                continue
            value = node.value
            if isinstance(value, ast.Attribute) and value.attr == "parents":
                raise AssertionError(
                    f"{module.name} line {node.lineno} walks up out of the "
                    f"package to find content. Use resources.packaged(), "
                    f"which asks the import system where the package is."
                )


def test_the_collector_is_found_inside_the_package():
    from m365_governance.collecting import COLLECTOR

    assert COLLECTOR.is_file()
    assert packaged("collectors") in COLLECTOR.parents


def test_a_source_is_never_guessed_from_the_path():
    """`origin` is decided by whether the caller supplied a path, never by
    inspecting where the path happens to point. A user who passes the packaged
    directory explicitly has still supplied it, and the report says so."""
    explicit = resolve("rules", packaged("rules"))
    assert explicit.origin == "external"
    assert Source(path=packaged("rules"), origin="package").is_packaged
