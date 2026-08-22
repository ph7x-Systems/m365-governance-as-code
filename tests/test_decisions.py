"""The three semantic decisions, held in place by tests.

Each of these was a choice the documents did not fix. They are decided now,
and a test exists for each so the decision cannot be reversed by accident:
none of the three would fail any other check if it silently changed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from conftest import ROOT, evidence, rule, sabotage
from m365_governance.engine import evaluate, evaluate_rule
from m365_governance.reporting import to_markdown
from m365_governance.results import Outcome
from m365_governance.validator import validate_structure

# ---------------------------------------------------------------------------
# 1. A true condition is a failure
# ---------------------------------------------------------------------------


def test_a_true_condition_is_a_failure(site_rule):
    """`owners.count less-than 2` against one owner is true, and reports fail."""
    result = evaluate_rule(site_rule, evidence("site-one-owner"))
    assert result.outcome is Outcome.FAIL


def test_a_false_condition_is_a_pass(site_rule):
    result = evaluate_rule(site_rule, evidence("site-two-owners"))
    assert result.outcome is Outcome.PASS


def test_inverting_the_operator_inverts_the_result(site_rule):
    """The direction is not inferable from the file, so it is pinned here.

    Nothing else in the suite fails if the engine flips: the schema, the rule
    graph and every message still validate. Only this assertion notices.
    """
    inverted = sabotage(
        site_rule, lambda r: r["condition"].update(operator="greater-than-or-equal")
    )
    assert evaluate_rule(inverted, evidence("site-two-owners")).outcome is Outcome.FAIL
    assert evaluate_rule(inverted, evidence("site-one-owner")).outcome is Outcome.PASS


def test_a_documented_limit_states_the_limit_next_to_the_observed_value():
    """The reader sees both numbers without following the link."""
    data = rule("SPO-LIST-001")
    assert data["basis"]["type"] == "documented-limit"
    limit = data["basis"]["limit"]["value"]
    fail_message = data["outcomes"]["fail"]["message"]
    assert f"{limit:,}" in fail_message, (
        f"the fail message must state the limit ({limit:,}) beside the observed value"
    )
    assert "{" + data["condition"]["evidence"] + "}" in fail_message


# ---------------------------------------------------------------------------
# 2. The engine may derive a documented fact, and never invent one
# ---------------------------------------------------------------------------


def test_a_derived_count_carries_its_bound_and_its_state(site_rule):
    result = evaluate_rule(site_rule, evidence("site-partial-expansion-decides"))
    used = {e.path: e for e in result.evidence_used}["owners.count"]
    assert used.exact is None
    assert used.lower_bound == 3
    assert used.state == "partial"
    assert used.detail and "lower bound" in used.detail


def test_a_bound_is_printed_as_a_bound_and_never_as_a_value(site_rule):
    """`at least 3` may never render as `3`."""
    result = evaluate_rule(site_rule, evidence("site-partial-expansion-decides"))
    assert "at least 3" in result.message
    assert "has 3 owners" not in result.message


def test_the_derivation_appears_in_both_report_formats():
    run = evaluate([rule("SPO-SITE-001")], evidence("site-partial-expansion-decides"))
    markdown = to_markdown(run)
    assert "at least 3" in markdown

    payload = json.loads(json.dumps(run.to_dict()))
    used = payload["results"][0]["evidence_used"][0]
    assert used["value"] is None
    assert used["lower_bound"] == 3
    assert used["state"] == "partial"


def test_the_engine_does_not_invent_a_count_when_the_bound_is_absent(site_rule):
    """No expansion fields at all is unknown, not zero."""
    broken = sabotage(
        evidence("site-partial-expansion-decides"),
        lambda d: d["facts"]["owners"].pop("minimum_count"),
    )
    assert evaluate_rule(site_rule, broken).outcome is Outcome.UNKNOWN


# ---------------------------------------------------------------------------
# 3. No composition in the grammar
# ---------------------------------------------------------------------------


def _schema_problems(document: dict) -> list:
    return validate_structure(document, "rule.schema.json", "<test>")


def test_a_composed_condition_is_rejected(site_rule):
    broken = copy.deepcopy(site_rule)
    broken["condition"] = {
        "all_of": [
            {"operator": "less-than", "evidence": "owners.count", "value": 2},
            {"operator": "equals", "evidence": "owners.count", "value": 0},
        ]
    }
    assert _schema_problems(broken)


def test_a_condition_with_two_evidence_paths_is_rejected(site_rule):
    broken = sabotage(
        site_rule, lambda r: r["condition"].update(evidence_2="owners.total")
    )
    assert _schema_problems(broken)


def test_two_facts_are_expressed_as_applicability_plus_condition():
    """The shape that replaces a conjunction, and why it is better.

    A conjunction would report `pass` for a list that already has unique
    permissions. Applicability reports `not-applicable`, which is a different
    line in the report and a truthful one: the rule had nothing to say.
    """
    list_rule = rule("SPO-LIST-001")
    assert list_rule["applicability"]["evidence"] == "permissions.inheritance_broken"
    assert list_rule["condition"]["evidence"] == "items.count"

    result = evaluate_rule(list_rule, evidence("list-unique-permissions"))
    assert result.outcome is Outcome.NOT_APPLICABLE
    assert not result.outcome.is_answer


# ---------------------------------------------------------------------------
# public architecture, private strategy
# ---------------------------------------------------------------------------

# public-scope-check: this file names the words it forbids
#: What a commercial strategy leaks, and none of it helps somebody using or
#: contributing to the project today. Published once, it is indexed, quoted and
#: copied, and a figure written before there is anything to sell becomes a
#: public promise the product may not want to keep a year later.
STRATEGY = (
    # Two digits or a separator: `$0` and `$1` are shell positional parameters
    # and a price is never written as a lone digit. The first version flagged
    # every script in tools/, which is how a guard teaches people to skip it.
    r"€\s*\d[\d,.]",
    r"\$\s*\d[\d,.]",
    r"\bpricing\b",
    r"\bperpetual licen[cs]e\b",
    r"\bbuy licen[cs]e\b",
    r"\bpaid tier\b",
    r"\bpurchase flow\b",
    r"\bSublime\b",
    r"\bWinRAR\b",
    r"\bAvalonia\b",
    r"\bWorkbench\b",
    r"\bPhase [012]\b",
    # Licensing mechanics, which are strategy even when no figure is attached.
    r"\blicen[cs]e key\b",
    r"\bactivation\b",
    r"\bentitlement\b",
    # OURS, NOT THE VENDOR'S. This was `\btrial\b` and it flagged
    # `companySubscription.isTrial`, a Microsoft field a licensing collector
    # must record, and every quotation of Microsoft's own wording about it.
    # A guard that fires on the vocabulary of the thing being governed is how a
    # guard teaches people to skip it, which this file already learnt once when
    # `$0` flagged every shell script in tools/.
    #
    # What is forbidden is pH7x's commercial model, so the patterns say so.
    r"\btrial (?:period|licen[cs]e|version)\b",
    r"\b(?:start|begin|extend) (?:a |your )?trial\b",
    r"\b\d+[- ]day trial\b",
    r"\bfree trial of\b",
    r"\bupgrade to\b",
    # Asking for money, in any form. This repository is the product: it
    # explains the software, documents how it is licensed today, and asks for
    # nothing. Support for the writing and the research belongs on ph7x.com,
    # where the thing being supported is the publishing.
    #
    # It was an allowed exception until 8 August 2026 and that is what made the
    # ambiguity possible: "the coffee link stays" was read as everywhere rather
    # than as on the site. A named exception is a decision somebody has to
    # remember; a forbidden pattern is one they cannot forget.
    r"\bbuymeacoffee\b",
    r"\bbuy me a coffee\b",
    r"\bsponsor\b",
    r"\bdonate\b",
    # Who pays and why. Added after a comment reading "the report a buyer
    # actually reads" and a commit message saying "nobody buys JSON" reached
    # this repository with every gate green: the vocabulary did not cover them
    # and the scan did not look at code or at commit messages. Both halves were
    # the hole.
    r"\bbuyer\b",
    r"\bbuyers\b",
    r"\bwho buys\b",
    r"\bnobody buys\b",
    r"\bselling\b",
    r"\bgo-to-market\b",
    r"\brevenue\b",
    r"\bwillingness to pay\b",
    r"\bARR\b",
)

#: DELIBERATELY ABSENT, and it is not an oversight. `customer`, `commercial`
#: and `sell` all have legitimate technical uses here: evidence a customer
#: receives, the licence's own wording, `no commercial licence is available`.
#: Forbidding them would fail on correct text, and a guard that fails on
#: correct text is one people learn to skip. Where a regex cannot separate a
#: technical use from a strategic one, the reviewer decides and this guard
#: stays quiet rather than crying wolf.
AMBIGUOUS_AND_ALLOWED = ("customer", "commercial", "sell")


def test_the_public_repository_explains_the_software_not_the_strategy():
    """The full documents exist, privately. This repository says what the
    software is and how to use it; the commercial model lives outside it.

    Not secrecy for its own sake: LICENSING.md states plainly that there is no
    commercial licence today and what will happen when there is. What it does
    not do is publish a figure, a phase or a roadmap that nobody can act on.
    """
    import re  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    # Only what git actually carries. The first version globbed the working
    # tree, and flagged a maintainer's local working file that this repository
    # does not ship: a guard that fails on files nobody receives teaches people
    # to ignore it.
    # EVERYTHING GIT CARRIES, not only the Markdown. The first version scanned
    # `*.md` because that is where a roadmap would obviously go, and a section
    # comment inside a module reached the repository untouched. A schema
    # description ships to every consumer that vendors the bundle; a code
    # comment is read by everyone who opens the file. Neither is more private
    # than a document.
    tracked = [
        path
        for path in subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
        if path.rsplit(".", 1)[-1]
        in ("md", "py", "json", "yaml", "yml", "sh", "ps1", "psm1", "toml", "cs")
        # Fixtures record what a system returned. They are read, not written.
        and not path.startswith("src/m365_governance/data/fixtures/")
    ]

    # A guard has to be able to name what it forbids, and so does a test that
    # asserts absence. The exemption is a marker inside the file rather than a
    # list here: a list of exempt paths is edited by whoever is being caught,
    # and a marker is visible to whoever opens the file.
    EXEMPT = "public-scope-check: this file names the words it forbids"
    tracked = [
        path
        for path in tracked
        if EXEMPT not in (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    ]

    # The changelog records what happened, including decisions later reversed.
    # A changelog that cannot say "this was added" because it was afterwards
    # removed is a changelog that lies, and this guard is about what the
    # repository says now rather than about what it once did.
    tracked = [name for name in tracked if name != "CHANGELOG.md"]

    offenders = []
    for path in (ROOT / name for name in sorted(tracked)):
        text = path.read_text(encoding="utf-8")
        for pattern in STRATEGY:
            for hit in re.finditer(pattern, text, re.IGNORECASE):
                line = text.count("\n", 0, hit.start()) + 1
                offenders.append(f"{path.name}:{line} {hit.group(0)!r}")
    # The commit messages this branch adds. A message is published forever the
    # moment the branch is, it is quoted in release notes and read on GitHub,
    # and until today nothing looked at one. Published history stays as it is.
    base = "origin/main"
    if (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", base],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        == 0
    ):
        unpublished = subprocess.run(
            ["git", "rev-list", f"{base}..HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        for commit in unpublished:
            message = subprocess.run(
                ["git", "log", "-1", "--format=%B", commit],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            # A message describing this guard has to be able to quote it, on
            # the same terms as a file: the marker is in the message, where a
            # reader of the log sees it, and not in a list of exempt hashes
            # that nobody reviews.
            if EXEMPT in message:
                continue
            for pattern in STRATEGY:
                for hit in re.finditer(pattern, message, re.IGNORECASE):
                    offenders.append(f"commit {commit[:8]} {hit.group(0)!r}")

    assert not offenders, "commercial strategy in the public repository: " + str(
        offenders
    )


# ---------------------------------------------------------------------------
# a validation observes; the engine concludes
# ---------------------------------------------------------------------------

#: Words that assert a governance conclusion. A validation script may not write
#: any of them: it captures what a tenant returned, and what that means is the
#: engine's answer from that evidence.
VERDICTS = (
    r"\bcompliant\b",
    r"\bnon-compliant\b",
    r"\bsecure\b",
    r"\binsecure\b",
    r"\bsafe\b",
    r"\bunsafe\b",
    r"\brisky\b",
    r"\bgood\b",
    r"\bbad\b",
    r"\bhealthy\b",
    r"\bpasses\b",
)


def test_a_validation_records_observations_and_never_a_verdict():
    """The convenient failure this prevents is three months away, not today.

    A validation script that starts saying `safe` or `compliant` because
    somebody found it useful has become a second rule engine, unreviewed, with
    no basis and no evidence requirements. The tenant is observed here; the
    conclusion is the engine's, from the evidence this captures.
    """
    import re  # noqa: PLC0415

    scripts = sorted((ROOT / "tools").glob("validate-*.ps1"))
    assert scripts, (
        "no validation script found; this guard would pass by walking nothing"
    )

    offenders = []
    for path in scripts:
        # The comment block names the forbidden words in order to forbid them.
        text = path.read_text(encoding="utf-8")
        body = text.split("#>", 1)[1] if "#>" in text else text
        for pattern in VERDICTS:
            for hit in re.finditer(pattern, body, re.IGNORECASE):
                line = body.count("\n", 0, hit.start()) + 1
                offenders.append(f"{path.name}:{line} {hit.group(0)!r}")

    assert not offenders, "a validation may not conclude: " + str(offenders)


def test_a_validation_leaves_a_fixture_with_no_tenant_in_it():
    """A run that only produces a report improves nothing permanently.

    And a fixture carrying a real tenant would put somebody's estate in a
    public repository, so the shape is kept and the identity is replaced.
    """
    script = (ROOT / "tools" / "validate-sandbox.ps1").read_text(encoding="utf-8")

    assert "fixtures/sharepoint" in script, "the run leaves no fixture behind"
    assert "contoso" in script, "the fixture must carry a placeholder tenant"


def test_no_tracked_file_names_the_tenant_the_owner_tests_against():
    """It looked at ONE script, and the name was in a document.

    The guard above checked the validation script alone, which is where the
    name was most likely to appear and is not where it appeared: the execution
    queue carried the host of the tenant the owner authorises tests against,
    written down as the thing not to publish. A host is a live tenant value
    like any other, and this repository ships to anyone.

    So it reads everything tracked. The one place the name is allowed is this
    file, which has to say the word in order to forbid it.
    """
    root = Path(__file__).resolve().parents[1]
    here = Path(__file__).resolve()
    offenders = []
    for folder in ("src", "tools", "docs", "tests", "examples"):
        base = root / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in {
                ".py",
                ".sh",
                ".md",
                ".json",
                ".yaml",
                ".psm1",
                ".ps1",
            }:
                continue
            if path.resolve() == here:
                continue
            if "y75hx" in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(path.relative_to(root)))
    assert not offenders, (
        f"a real tenant host reached tracked files: {offenders}. It is not a "
        "hostname in a document; it is somebody's estate in a public "
        "repository."
    )


def test_the_public_repository_names_no_private_consumer():
    """A public engine must not know who consumes it.

    Naming a particular private product here makes an open repository depend on
    knowing about a closed one, and the next consumer arrives to find the
    engine shaped around somebody else. It was worse than a comment in one
    place: `consumed_by` is SHIPPED TEXT, so a customer's evidence carried the
    name of a product they do not have.

    The generator's own docstring already says this. This is the part that
    fails when somebody forgets.
    """
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for folder in ("src", "tools", "docs"):
        for path in (root / folder).rglob("*"):
            if path.suffix not in {
                ".py",
                ".sh",
                ".md",
                ".json",
                ".yaml",
                ".psm1",
                ".ps1",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "Workbench" in text:
                offenders.append(str(path.relative_to(root)))

    assert not offenders, (
        "the public repository names a private consumer in: " + ", ".join(offenders)
    )
