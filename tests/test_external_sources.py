"""The external-source licence gate.

Discovery reads other people's work. Using it is a separate decision, and the
only version of that decision worth having is one a machine re-checks: a rule
that lives in somebody's memory is a rule that holds until the day it matters.

The register is `docs/EXTERNAL-SOURCES.json`. These tests fail when

  - a record is missing a field the decision depends on;
  - an intended use outruns the permissions recorded beside it;
  - a source the repository references has no record at all.

**No licence found is not permission.** An unresolved licence blocks reuse and
never blocks discovery: facts and public API behaviour stay investigable, and
the executor may conclude that nothing needed copying in the first place.
"""

from __future__ import annotations

import json
import re

import pytest

from conftest import ROOT

REGISTER = ROOT / "docs" / "EXTERNAL-SOURCES.json"

#: Read once. A parse failure here fails every test below, which is the right
#: blast radius for a malformed register.
DOCUMENT = json.loads(REGISTER.read_text(encoding="utf-8"))
SOURCES = DOCUMENT["sources"]
LEVELS = DOCUMENT["intended_use_levels"]

#: Every record answers all of these. A field left out is not a permissive
#: default; it is a question nobody asked.
REQUIRED = (
    "id",
    "repository",
    "publisher",
    "license",
    "license_source",
    "code_reuse",
    "modification",
    "redistribution",
    "attribution",
    "content_license_differs",
    "intended_use",
    "use_note",
    "verified",
)

#: What each intended use demands of the permissions recorded above it. The two
#: reading levels demand nothing, which is the point: **an unknown licence stops
#: reuse, not investigation.**
DEMANDS = {
    "factual-discovery": (),
    "reference-only": (),
    "runtime-dependency": (),
    "adapted-implementation": ("modification", "redistribution"),
    "copied-code": ("code_reuse", "modification", "redistribution"),
    "upstream-contribution": (),
}

#: A licence value that resolves to no grant. Recorded rather than left null so
#: that "we looked and found nothing" reads differently from "nobody looked".
UNRESOLVED = {None, "", "none-found", "unknown", "proprietary"}

#: Where the completeness scan looks, and what it looks for. Bare `owner/repo`
#: is matched only for publishers already known to this project, because a
#: general pattern for it matches half of every file path in the repository.
#: The bound is real and worth stating: a brand new publisher mentioned in
#: prose without its URL is not caught here, which is why the contract asks for
#: the full URL. Written as a URL, it is caught exactly.
SCANNED = ("docs", "src", "tools")
SUFFIXES = {".md", ".py", ".ps1", ".psm1", ".json", ".sh", ".yaml"}
KNOWN_PUBLISHERS = ("pnp", "SharePoint", "microsoft", "MicrosoftDocs", "OfficeDev")
URL_MENTION = re.compile(r"github\.com/([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)")
BARE_MENTION = re.compile(
    r"(?<![\w/.-])(" + "|".join(KNOWN_PUBLISHERS) + r")/([A-Za-z0-9._-]+)(?![\w.-])"
)

#: This file names every source in order to check them, so scanning it would
#: only ever find what it already knows.
SELF = REGISTER.name


def registered() -> set[str]:
    return {s["id"] for s in SOURCES}


def mentions() -> dict[str, set[str]]:
    """Every external source named anywhere that ships, and where."""
    found: dict[str, set[str]] = {}
    for directory in SCANNED:
        for path in (ROOT / directory).rglob("*"):
            if not path.is_file() or path.name == SELF:
                continue
            if path.suffix not in SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name in URL_MENTION.findall(text):
                found.setdefault(name.removesuffix(".git"), set()).add(str(path))
            for owner, repo in BARE_MENTION.findall(text):
                found.setdefault(f"{owner}/{repo}", set()).add(str(path))
    return found


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_every_record_answers_every_question(source):
    missing = [field for field in REQUIRED if field not in source]
    assert not missing, f"{source.get('id')} does not record {missing}"


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_every_intended_use_is_a_declared_level(source):
    unknown = set(source["intended_use"]) - set(LEVELS)
    assert not unknown, (
        f"{source['id']} claims {sorted(unknown)}, which no level defines. "
        "Add the level and what it demands, or use one that exists."
    )


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_intended_use_does_not_outrun_the_permissions(source):
    """Licence compatibility is evaluated against the intended use, not against
    the repository's reputation. Reading behaviour is not copying an
    implementation, and referencing an API is not redistributing source."""
    for use in source["intended_use"]:
        for permission in DEMANDS[use]:
            assert source[permission] is True, (
                f"{source['id']} claims {use}, which needs {permission}, and "
                f"the register says {source[permission]!r}."
            )


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_an_unresolved_licence_permits_reading_and_nothing_else(source):
    """No licence found is not permission."""
    if source["license"] not in UNRESOLVED:
        return
    beyond_reading = [use for use in source["intended_use"] if DEMANDS[use]]
    assert not beyond_reading, (
        f"{source['id']} has licence {source['license']!r} and claims "
        f"{beyond_reading}. Resolve the licence first; discovery is unaffected."
    )
    assert source["code_reuse"] is False


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_contribution_upstream_needs_terms_that_somebody_read(source):
    if "upstream-contribution" not in source["intended_use"]:
        return
    assert source.get("contribution_terms"), (
        f"{source['id']} intends to contribute upstream and records no "
        "contribution terms. Find them, or say where the search stopped."
    )


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["id"])
def test_a_differing_content_licence_is_explained(source):
    """Documentation and code are commonly not under the same terms, and the
    difference is the part that gets missed."""
    if source["content_license_differs"]:
        assert source.get("content_license_note")


def test_every_source_the_repository_names_is_registered():
    """The gate that cannot be forgotten: naming a source anywhere that ships
    puts it in the register, or this fails and says which file named it."""
    known = registered()
    unregistered = {
        name: sorted(where) for name, where in mentions().items() if name not in known
    }
    assert not unregistered, (
        "external sources named with no licence record: "
        + json.dumps(unregistered, indent=2)
    )


def test_the_scan_actually_finds_things():
    """A completeness check that silently matches nothing passes forever. This
    is the test that notices."""
    assert len(mentions()) >= 2
