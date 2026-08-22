"""`SPO-SCRIPT-001`, and the two ways it could have been wrong.

**THE FIELD IT READS RAN THE OTHER WAY.** The evidence fact was called
`custom_script` and held `DenyAddAndCustomizePages`, so true meant custom script
is BLOCKED. A rule written against that name would have reported every protected
site as permissive and every open one as safe. The fact is now named for the
direction the boolean runs.

**AND A PASS MAY DESCRIBE A DEFAULT RATHER THAN A DECISION.** Microsoft
announced in `MC1117115` that custom scripting became disabled by default on
classic publishing sites on 15 September 2025, and that the tenant-level opt-out
retired on 15 March 2026. Neither date is derivable from the reference pages
this rule otherwise rests on. Observing correctly and concluding falsely is
still concluding falsely, so the limitation is carried and the announcement is a
source.
"""

from __future__ import annotations

import json

import pytest
import yaml

from conftest import DATA

RULE = DATA / "rules" / "sharepoint" / "SPO-SCRIPT-001.yaml"
FIXTURES = DATA / "fixtures" / "sharepoint"


@pytest.fixture(scope="module")
def rule():
    with RULE.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def facts(name):
    with (FIXTURES / f"site-customization-{name}.json").open(
        encoding="utf-8"
    ) as handle:
        return json.load(handle)["facts"]["customization"]


def test_the_fact_is_named_for_the_direction_it_runs(rule):
    """A boolean whose name does not say which way it points is a rule waiting
    to be inverted by whoever writes the next one."""
    assert rule["condition"]["evidence"] == "customization.custom_script_denied"
    assert rule["condition"]["value"] is False

    for name in ("surfaces-observed", "script-permitted", "pages-feature-absent"):
        fact = facts(name)["custom_script_denied"]

        assert isinstance(fact["value"], bool), name
        assert fact["raw"]["field"] == "DenyAddAndCustomizePages", name

    # And the old name is gone, so nothing can read it by accident.
    assert "custom_script" not in facts("surfaces-observed")


def test_every_outcome_has_a_fixture_that_reaches_it():
    """A rule whose fail path no fixture reaches has never run."""
    assert facts("script-permitted")["custom_script_denied"]["value"] is False
    assert facts("surfaces-observed")["custom_script_denied"]["value"] is True
    assert facts("tenant-read-not-made")["custom_script_denied"]["state"] == "missing"


def test_a_pass_never_claims_the_site_is_inert(rule):
    """BLOCKED IS NOT INERT, and it is the misreading the control invites.

    Microsoft lists nine extensions that blocking stops, and `.html` is not
    among them; writing about Content Security Policy they state it from the
    other side, that added script will not execute and added HTML will still
    work.
    """
    passing = rule["outcomes"]["pass"]["message"]
    unresolved = rule["limitations"]["passes_without_resolving"]

    assert "blocked" in passing.lower()
    for word in ("safe", "inert", "secure", "protected"):
        assert word not in passing.lower(), word

    for extension in (".aspx", ".htc", ".master", ".xap"):
        assert extension in unresolved, extension
    assert "`.html` and `.htm` are not among them" in unresolved


def test_an_unread_setting_is_not_a_pass(rule):
    """The setting comes from a tenant-scoped read. A run that did not make one
    has established nothing, and the message has to say so where a reader is."""
    unknown = rule["outcomes"]["unknown"]["message"]

    assert "not a pass" in unknown.lower()
    assert "tenant-scoped" in unknown


def test_the_announced_change_is_a_source_and_not_a_footnote(rule):
    """Learn says what the product does. It does not say what it is about to
    stop doing, and this change moves what a pass MEANS."""
    sources = rule["basis"]["sources"]

    announced = [s for s in sources if "MC1117115" in s["title"]]
    assert announced, "the announcement that changed the default is not a source"

    title = announced[0]["title"]
    assert "15 September 2025" in title
    assert "15 March 2026" in title
    assert announced[0]["publisher"] == "Microsoft"

    # AND THE LIMITATION IS ON THE RULE, where a reader of a pass meets it.
    other = " ".join(rule["limitations"]["other"])
    assert "MC1117115" in other
    assert "default rather than a decision" in other.lower()


def test_the_basis_is_advice_and_says_so(rule):
    """Microsoft recommends; nothing in the product forbids it. A rule claiming
    otherwise would publish a violation where a tenant made a choice."""
    assert rule["basis"]["type"] == "documented-guidance"
    assert "not a requirement" in rule["basis"]["rationale"]
