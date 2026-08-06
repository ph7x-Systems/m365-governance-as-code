"""What each outcome means, and what it does not.

The whole project rests on six words being different from each other. Leaving
that distinction in a README means it is read once, by somebody who has not yet
seen a report, and never again by the person holding one.

Each entry says what the outcome means, what it is not, how it aggregates,
what a pipeline does with it, and shows a line from a real report. The "is
not" section is the one that matters: every outcome here has a wrong reading
that is more comfortable than the right one.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from .results import Outcome

WIDTH = 76


def _fill(text: str, indent: str = "", hanging: str | None = None) -> str:
    return textwrap.fill(
        " ".join(text.split()),
        width=WIDTH,
        initial_indent=indent,
        subsequent_indent=hanging if hanging is not None else indent,
        # A flag is one word. Without this, textwrap split
        # `--fail-on-regression` across two lines at a hyphen and produced
        # something nobody could copy.
        break_on_hyphens=False,
    )


@dataclass(frozen=True)
class Explanation:
    outcome: Outcome
    meaning: str
    is_not: list[str]
    aggregation: str
    pipeline: list[str]
    example: str

    def render(self) -> str:
        lines = [self.outcome.value.upper(), "", _fill(self.meaning), ""]
        lines.append("This is not")
        lines.extend(_fill(f"- {item}", "  ", "    ") for item in self.is_not)
        lines.append("")
        lines.append("How it aggregates")
        lines.append(_fill(self.aggregation, "  "))
        lines.append("")
        lines.append("In a pipeline")
        lines.extend(_fill(f"- {item}", "  ", "    ") for item in self.pipeline)
        lines.append("")
        lines.append("Example")
        # The example is verbatim from a report, so it is never re-wrapped:
        # a line break inside a finding is part of how the finding reads.
        lines.extend(f"  {line}".rstrip() for line in self.example.strip().splitlines())
        return "\n".join(lines) + "\n"


EXPLANATIONS: dict[Outcome, Explanation] = {
    Outcome.PASS: Explanation(
        outcome=Outcome.PASS,
        meaning=(
            "The rule applied to this resource, the evidence it needed was "
            "readable, and the condition it reports was not found."
        ),
        is_not=[
            "a statement that the resource is safe;",
            "a statement that the risk behind the rule is resolved;",
            "permanent. It is true of the evidence collected, on the day it "
            "was collected.",
        ],
        aggregation=(
            "Counts as an answer. It is one of only two outcomes that "
            "establish anything about the resource."
        ),
        pipeline=[
            "never fails a build;",
            "leaving `pass` for anything else is a regression, and "
            "`diff --fail-on-regression` exits non-zero on it.",
        ],
        example="""
The site has 2 owners.

**This pass does not establish:** Two owners who are dormant, who have left,
or who do not know they own the site satisfy this rule completely.
""",
    ),
    Outcome.FAIL: Explanation(
        outcome=Outcome.FAIL,
        meaning=(
            "The rule applied, the evidence was readable, and the condition it "
            "reports was found. A condition names the case worth reporting, so "
            "finding it is a failure."
        ),
        is_not=[
            "necessarily urgent. Severity is a separate field with its own "
            "rationale, and it is deliberately independent of `basis`;",
            "necessarily a rule you have to follow. A `convention` or an "
            "`opinion` can fail, and a reasonable organisation may decline it. "
            "Read the basis before the finding.",
        ],
        aggregation=(
            "Counts as an answer. The report leads with these, and each one "
            "carries the evidence it came from."
        ),
        pipeline=[
            "`evaluate --fail-on fail` exits non-zero;",
            "`evaluate --fail-on unresolved` exits non-zero.",
        ],
        example="""
The list holds 148000 items, above Microsoft's documented limit of 100,000,
and still inherits its permissions.

- Basis: documented-limit
- Evidence: `items.count` = 148000
""",
    ),
    Outcome.UNKNOWN: Explanation(
        outcome=Outcome.UNKNOWN,
        meaning=(
            "The rule could not be decided from the evidence collected. What "
            "is missing could still change the answer."
        ),
        is_not=[
            "compliance. This is the reading the whole project exists to prevent;",
            "a failure of the resource. It is a fact about the collection;",
            "the same as incomplete evidence. Incomplete evidence often still "
            "decides: three owners and one unexpanded group proves `at least "
            "three`, and a rule asking for two passes on it. `unknown` is "
            "returned only when the missing part could change the outcome.",
        ],
        aggregation=(
            "Never aggregated as a pass. The report counts it separately and "
            "says in words that it is not compliance."
        ),
        pipeline=[
            "`evaluate --fail-on unresolved` exits non-zero;",
            "`evaluate --fail-on fail` does not, which is why `unresolved` is "
            "the setting to use;",
            "moving from `pass` to `unknown` is a regression: the answer was "
            "lost, and losing an answer is not neutral.",
        ],
        example="""
The owners of this site were not collected, so the number is not known.
This is not a pass.

- Evidence: `owners.count` = <permission-denied>
""",
    ),
    Outcome.NOT_APPLICABLE: Explanation(
        outcome=Outcome.NOT_APPLICABLE,
        meaning=(
            "The rule does not speak about this resource. Its applicability "
            "was evaluated and not met, so the rule had nothing to say."
        ),
        is_not=[
            "a pass. A rule that never applied established nothing;",
            "an error. It is the correct outcome, and often the honest one: a "
            "list that already has unique permissions cannot lose an option it "
            "has already taken;",
            "the same as `unknown`. Here the rule was decided; it decided that "
            "it does not apply.",
        ],
        aggregation=(
            "Counted separately, and never as an answer. A report that shows "
            "'12 of 12 rules did not fail' while ten were not applicable is "
            "reporting nothing."
        ),
        pipeline=[
            "never fails a build on its own;",
            "moving from `pass` to `not-applicable` is still flagged by "
            "`diff --fail-on-regression`, and that is deliberate. It is often "
            "legitimate, and it always means an answer you had yesterday is "
            "gone today. Somebody should see it and say so.",
        ],
        example="""
This list already has unique permissions. The limit does not remove an
option it has already exercised.
""",
    ),
    Outcome.INVALID_EVIDENCE: Explanation(
        outcome=Outcome.INVALID_EVIDENCE,
        meaning=(
            "A value the rule needed came back in a form it cannot evaluate: "
            "a word where an integer was declared, a structure that does not "
            "match the evidence schema."
        ),
        is_not=[
            "the same as `unknown`, and the difference is the fix. `unknown` "
            "is fixed by collecting again; this is fixed by repairing the "
            "collector or the schema;",
            "a finding about the resource. Nothing has been established about "
            "the tenant here;",
            "something to retry. Running it again produces the same thing.",
        ],
        aggregation=(
            "Counted with `unknown` as unresolved, never as a pass. It is "
            "resolved first of all the outcomes, so a malformed value cannot "
            "disappear beneath an applicability decision."
        ),
        pipeline=[
            "`evaluate --fail-on unresolved` exits non-zero;",
            "treat it as a bug report against the collector, not as a "
            "governance finding.",
        ],
        example="""
The item count was returned in a form this rule cannot evaluate. The
collector output does not match the evidence schema.

  facts.items.count: { state: invalid, raw: { field: ItemCount, value: "many" } }
""",
    ),
    Outcome.ERROR: Explanation(
        outcome=Outcome.ERROR,
        meaning=(
            "The evaluation did not finish. A bug, a crash, a malformed rule "
            "that got past validation."
        ),
        is_not=[
            "a statement about the resource, in any direction;",
            "authorable by a rule. It is the one outcome a rule may not write "
            "a message for, because it describes the engine rather than the "
            "thing being checked. A rule that could describe its own failure "
            "would be describing something it cannot observe;",
            "something to interpret. Read the engine detail and fix the tool.",
        ],
        aggregation=(
            "Counted separately and never as an answer. If any appear, the "
            "run is not a report yet."
        ),
        pipeline=[
            "`evaluate --fail-on unresolved` exits non-zero;",
            "an error in a governance run should stop the pipeline, not colour a cell.",
        ],
        example="""
The evaluation did not finish. This describes the engine, not the resource,
and no conclusion may be drawn from it.

- Engine: KeyError: 'outcomes'
""",
    ),
}

#: The order a person meets them in: the two that answer, then the three that
#: do not, then the one that is about us.
ORDER = [
    Outcome.PASS,
    Outcome.FAIL,
    Outcome.UNKNOWN,
    Outcome.NOT_APPLICABLE,
    Outcome.INVALID_EVIDENCE,
    Outcome.ERROR,
]

NAMES = [outcome.value for outcome in ORDER]


def explain(name: str) -> str:
    if name == "all":
        parts = [EXPLANATIONS[o].render() for o in ORDER]
        header = (
            _fill(
                "Six outcomes. Two of them answer a question about a "
                "resource; three say the question was not answered, each for "
                "a different reason; one is about the tool."
            )
            + "\n\n"
            + _fill("Nothing here aggregates as a pass except a pass.")
            + "\n"
        )
        return header + "\n" + ("\n" + "-" * 72 + "\n\n").join(parts)

    try:
        outcome = Outcome(name)
    except ValueError as exc:
        raise KeyError(
            f"no outcome called {name!r}. Try one of: {', '.join(NAMES)}, or all"
        ) from exc
    return EXPLANATIONS[outcome].render()
