"""Two lists, one containment, and nothing else generalised.

`tools/coverage.py` holds a subject vocabulary and a set of coverage domains,
and they answer different questions:

    SUBJECT_VOCABULARY   what subjects exist
    COVERAGE_DOMAINS     what the engine promises to cover end to end

They used to be one list, which asked every subject worth writing about to also
be one the engine covers with rules, collectors, fixtures, tests and a Compass
route. Agents is the counter-example: three articles, zero rules, and **zero
rules is the correct state there** because nothing documented supports one yet.

These tests hold the containment in one direction and nothing more. There is no
abstraction over *kinds of domain* here on purpose: two lists and a subset test
are enough until a third behaviour actually turns up.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Loaded by path under a different name on purpose. `tools/coverage.py` shares
#: its name with the coverage library, so putting `tools/` on sys.path shadows
#: it and the release contract's own coverage step stops working. Found by
#: doing exactly that.
_spec = importlib.util.spec_from_file_location(
    "ph7x_coverage_tool", ROOT / "tools" / "coverage.py"
)
cov = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cov)


def test_every_coverage_domain_is_a_known_subject():
    """The containment, and it runs one way only. A domain the engine covers
    that nobody can classify content into is a taxonomy split in two."""
    unknown = set(cov.COVERAGE_DOMAINS) - set(cov.SUBJECT_VOCABULARY)
    assert not unknown, (
        f"{sorted(unknown)} are covered end to end and are not in the subject "
        "vocabulary. Add them there; the reverse is never required."
    )


def test_a_subject_is_not_a_coverage_domain_by_default():
    """The inverse must NOT hold, and this is the test that says so out loud.

    If it ever became true, somebody has quietly re-merged the lists and every
    new subject would arrive carrying an end-to-end obligation it never asked
    for."""
    subjects_only = set(cov.SUBJECT_VOCABULARY) - set(cov.COVERAGE_DOMAINS)
    assert subjects_only, (
        "every subject is now a coverage domain. Either that was an explicit "
        "commitment for each one, or the two lists have been merged again."
    )


def test_every_subject_has_a_name():
    for prefix, name in cov.SUBJECT_VOCABULARY.items():
        assert name and name != "unnamed domain", f"{prefix} has no name"
        assert prefix.isupper(), f"{prefix} is not an identifier"


@pytest.mark.parametrize("prefix", sorted(cov.SUBJECT_VOCABULARY))
def test_the_exported_vocabulary_says_whether_coverage_is_defined(prefix):
    """`0` and `not defined` are different answers, and the artefact has to
    carry the difference rather than leaving a reader to infer it.

    Zero means the obligation was measured and nothing was found. Not defined
    means the obligation does not exist for this subject. It is the same
    distinction as `unknown` never being `pass`."""
    subjects = cov.build()["subjects"]
    assert prefix in subjects
    expected = "defined" if prefix in cov.COVERAGE_DOMAINS else "not defined"
    assert subjects[prefix]["coverage"] == expected


def test_the_matrix_rows_are_the_coverage_domains_and_not_the_vocabulary():
    """A subject outside the commitment must not appear as an incomplete row.
    That would report a gap where there is no obligation, and the Domain
    Completion Gate would start blocking work on a promise nobody made."""
    rows = set(cov.build()["domains"])
    strays = rows - set(cov.COVERAGE_DOMAINS)
    assert not strays, (
        f"{sorted(strays)} appear in the coverage matrix without an end-to-end "
        "commitment. They would read as permanently incomplete."
    )
