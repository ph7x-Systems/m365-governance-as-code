"""The report a person receives, measured whole and frozen as bytes.

WHY THIS COMPARES AGAINST A FILE AND NOT AGAINST A RE-RENDER. The first
density measurement in this repository was wrong, and it was wrong in a way
that flattered the change: the `before` and the `after` were both rendered
with the corrected code, so the only difference that could appear was the one
already applied. A comparison assembled after the fact can only find what it
was built to find.

The correction is not to be more careful. It is to make the `before` a thing
that exists before the change: `tests/frozen/single-site-report.md` holds the
bytes this renderer produced on the day they were accepted. A renderer change
diffs against those bytes. Regenerating the file is how the measurement is
lost, so regenerating it is a deliberate act with a reviewer attached.

WHAT THE DOCUMENT IS. One site, six slices, composed exactly as `collect` and
`assess` compose them. The states are the ones a real tenant produced on
2026-08-18, preserved as fixtures under the rules in the fixtures README: a
stale site, a group-connected site with no label, owners behind an unexpanded
group, sharing decided beside the owners, a clean modern site, and storage in
pooled mode. Nothing here identifies anybody, and nothing here needs a tenant.

WHAT IT MEASURES. Line counts alone do not measure editorial weight -- the
446-character SPO-CLASS-003 message was one line -- so the size in characters
is part of the gate. And the whole document is measured, not the findings
block: a report is read from the top, and a preamble nobody needs costs the
same attention as a finding nobody needs.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from m365_governance import composing, engine
from m365_governance.loader import load_rules
from m365_governance.reporting import many_to_markdown
from m365_governance.resources import packaged
from m365_governance.results import RunSet

FROZEN = Path(__file__).parent / "frozen" / "single-site-report.md"

#: The slices that ran against one real site, each preserved as the state it
#: was in. Named rather than globbed: a fixture added for another reason must
#: not silently change what this document is.
SLICES = (
    "site-activity-stale",
    "site-class-group-unlabelled",
    "site-owners-group-not-expanded",
    "site-sharing-beside-owners",
    "site-modern-clean",
    "site-storage-no-quota",
)

#: A findings entry opens with its outcome in bold. Continuation lines are
#: indented, which is how a message is told from the next entry.
ENTRY = re.compile(r"^- \*\*(?P<outcome>[A-Za-z ]+)\*\*")


def _document() -> str:
    folder = packaged("fixtures") / "sharepoint"
    resource = json.loads(
        (folder / "site-class-group-unlabelled.json").read_text(encoding="utf-8")
    )["resource"]

    documents = []
    for name in SLICES:
        slice_ = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        # One site described six times. The fixtures carry six identities
        # because each is also used alone; here they are one resource, which
        # is the only reading under which composing them means anything.
        slice_["resource"] = copy.deepcopy(resource)
        documents.append(slice_)

    composed = composing.compose(documents)
    assert len(composed) == 1, "six slices about one site composed into more than one"

    rules = [rule.data for rule in load_rules(packaged("rules"))]
    return many_to_markdown(
        RunSet([engine.evaluate(rules, composed[0], only_collected=True)])
    )


def _weigh(document: str) -> dict[str, int]:
    """Every non-empty line, by what it asks of the reader.

    A line belongs to the entry it opens or continues, so a finding's message
    is counted as the finding and not as prose. Everything outside the entries
    is context: headings, the summary, and the notes about coverage and
    identity.
    """
    counts = {"action": 0, "remediation": 0, "unknown": 0, "hand-off": 0, "context": 0}
    current = "context"
    for line in document.splitlines():
        if not line.strip():
            continue
        found = ENTRY.match(line)
        if found:
            outcome = found.group("outcome")
            current = {
                "Fail": "action",
                "Invalid evidence": "action",
                "Error": "action",
                "Unknown": "unknown",
                "Not applicable": "hand-off",
            }.get(outcome, "context")
        elif not line.startswith("  "):
            current = "context"
        # Counted inside its finding and again on its own, because "does every
        # failure carry a first step" is the question this slice existed for
        # and a line total cannot answer it.
        if line.strip().startswith("**What to do:**"):
            counts["remediation"] += 1
        counts[current] += 1
    return counts


def test_the_report_is_the_bytes_that_were_accepted():
    """The frozen document, byte for byte.

    A renderer change lands here first. Read the diff: if it removes a line a
    reader needed, the diff says so before anybody has to notice it missing
    from a real report.
    """
    assert FROZEN.read_text(encoding="utf-8") == _document(), (
        f"the rendered report no longer matches {FROZEN.name}. If the change is "
        f"intended, write the new document into that file in the same commit, so "
        f"the next measurement compares against bytes and not against a re-render."
    )


def test_the_document_is_measured_whole_and_not_only_its_findings():
    """The four numbers, and the size.

    These are recorded, not required to improve. A gate that demanded fewer
    lines every time would eventually delete something a reader needs, and the
    point of the measurement is that somebody looks at it.
    """
    document = FROZEN.read_text(encoding="utf-8")
    counts = _weigh(document)

    assert counts == {
        "action": 12,
        "remediation": 4,
        "unknown": 2,
        "hand-off": 2,
        "context": 15,
    }, counts
    assert len(document) == 2967, len(document)
    assert (
        counts["action"] + counts["unknown"] + counts["hand-off"] + counts["context"]
        == 31
    ), counts

    # EVERY FAILURE CARRIES A FIRST STEP. This is the assertion the slice was
    # for: `assess` writes a run set, `many_to_markdown` renders it, and it
    # rendered the message and stopped. Four failures reached an administrator
    # with nothing to do about any of them.
    assert counts["remediation"] == document.count("- **Fail**")

    # Sixteen lines of findings over fifteen of preamble. It was twelve under
    # nineteen. Not asserted as a direction -- a gate that demanded the ratio
    # improve every time would eventually delete something a reader needs. It
    # is here so that the next person to change the renderer sees which half of
    # the document is larger, which measuring the findings alone could not show.
