#!/usr/bin/env python3
"""The product coverage matrix, derived rather than maintained.

A matrix somebody updates by hand is duplicated truth, and it starts lying
within a week — which is exactly the failure it exists to prevent. This reads
the repository and writes what it finds.

Two outputs:

    docs/DOMAIN-COVERAGE.json   the matrix, machine-readable
    docs/PRODUCT-STATE.md       the same numbers, for a person

`--check` regenerates into memory and fails if either file on disk differs.
The release contract runs that, so the matrix cannot rot silently.

**Site-side columns come from another repository.** Guide, Knowledge, Analysis
and Compass live in the corporate site, which references rule IDs, so the
coverage is derivable when that checkout is present. When it is not, those
columns are recorded as `unknown` with the path that was looked for — never as
zero. Inferring absence from not having looked is the one thing the whole
product refuses.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "m365_governance" / "data"
RULES = DATA / "rules"
PROFILES = DATA / "profiles"
TESTS = ROOT / "tests"
DOCS = ROOT / "docs"

#: Where the corporate site is expected. Override with PH7X_SITE.
SITE = Path(os.environ.get("PH7X_SITE", Path.home() / "dev" / "Ph7x.Site.Corporate"))

RULE_ID = re.compile(r"\b(SPO)-([A-Z]+)-(\d+)\b")

#: The columns that come from the corporate site rather than from here.
SITE_COLUMNS = ("knowledge", "guide", "analysis", "compass")

#: TWO LISTS, AND THEY MEAN DIFFERENT THINGS.
#:
#:     SUBJECT_VOCABULARY   what subjects exist
#:     COVERAGE_DOMAINS     what the engine promises to cover end to end
#:     domain               which subject an artefact belongs to
#:     coverage             how complete an engine domain is
#:
#: They were one list, which quietly asked every subject worth writing about to
#: also be a subject the engine covers with rules, collectors, fixtures, tests
#: and a Compass route. Agents is the counter-example that made it visible:
#: three articles, zero rules, and zero rules is the *correct* state there,
#: because nothing Microsoft documents supports one yet.
#:
#: > **A subject does not become a coverage domain because it has content. It
#: > becomes one only when the engine makes an explicit end-to-end coverage
#: > commitment for it.**
#:
#: The asymmetry travels to whoever reads the matrix: a coverage domain missing
#: a surface reports `0`, meaning *this obligation was measured and nothing was
#: found*. A subject outside COVERAGE_DOMAINS reports `not defined`, meaning
#: *this obligation does not exist here*. Same distinction as `unknown` never
#: being `pass`.

#: The authorised subject vocabulary. Every consumer of this engine classifies
#: against this one list, and naming a particular one here would make a public
#: repository depend on knowing about somebody's private product. The prefix
#: is an identifier and a heading is not, so the names live here too, and
#: `unnamed domain` appears if a new prefix arrives without one.
SUBJECT_VOCABULARY = {
    "ACTIVITY": "Activity",
    "CLASS": "Classification",
    "LIST": "Permissions",
    "MODERN": "Modernity",
    "SHARE": "Sharing",
    "SITE": "Sites and storage",
    "SPFX": "SPFx",
    # Subjects, deliberately not coverage domains.
    "AGENTS": "Agents and Copilot",
    "PLATFORM": "Platform and evidence",
}

#: What the engine commits to covering end to end. REQUIRED below applies to
#: these and to nothing else, so the Domain Completion Gate keeps the meaning
#: it has always had. Adding a subject above does not add an obligation here;
#: that is a separate, explicit decision.
COVERAGE_DOMAINS = (
    "ACTIVITY",
    "CLASS",
    "LIST",
    "MODERN",
    "SHARE",
    "SITE",
    "SPFX",
)

#: Which surfaces a domain has to reach before it may be called complete.
#: The Domain Completion Gate reads this.
#:
#: `analysis` is a column and deliberately not a gate: a post is written when a
#: lesson, trade-off or failure mode is left over that is neither Knowledge nor
#: Guide, and when there is none, not writing one is the correct outcome.
#: Requiring it would manufacture posts to turn a cell green.
#:
#: Explorer and graph coverage are not here because nothing in this repository
#: makes them derivable. Naming a column this tool cannot measure would be a
#: gap invented rather than observed.
REQUIRED = (
    "rules",
    "collector_modes",
    "fixtures",
    "tests",
    "profiles",
    "knowledge",
    "guide",
    "compass",
)


def rule_files() -> dict[str, list[str]]:
    """Domain → rule ids on disk."""
    out = defaultdict(list)
    for path in sorted(RULES.rglob("*.yaml")):
        match = RULE_ID.fullmatch(path.stem)
        if match:
            out[match.group(2)].append(path.stem)
    return dict(out)


def ids_by_domain(paths, pattern=RULE_ID) -> dict[str, set[str]]:
    """Domain → the distinct rule ids mentioned anywhere in these files."""
    out = defaultdict(set)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for _, domain, number in pattern.findall(text):
            out[domain].add(number)
    return dict(out)


def collector_modes() -> dict[str, str]:
    """Slice name → collector mode, and the profile that consumes it."""
    sys.path.insert(0, str(ROOT / "src"))
    from m365_governance import collecting  # noqa: PLC0415

    # Uma fatia que não produz achados não alimenta domínio nenhum, e incluí-la
    # aqui punha a `agents` a contar como modo de collector de TODOS os sete:
    # usa o perfil `default`, que seleciona todas as regras, portanto pertencia
    # a toda a gente. Um número que sobe em sete linhas por causa de uma fatia
    # que não avalia nada é cobertura inventada.
    return {
        s.name: (s.mode, s.profile)
        for s in collecting.SLICES.values()
        if s.produces_findings
    }


def profile_rules(every: list[str]) -> dict[str, list[str]]:
    """Profile name → the rule ids it selects.

    A profile with no `rules` key selects everything, which is what `default`
    is for and what the classification slice is paired with. Recording it as
    selecting nothing would report classification as having no collector, and
    a matrix that invents a gap sends somebody to fix what is not broken.
    """
    import yaml  # noqa: PLC0415

    out = {}
    for path in sorted(PROFILES.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        out[path.stem] = loaded.get("rules") or every
    return out


def fixtures_by_domain(on_disk: dict[str, list[str]]) -> dict[str, list[str]]:
    """Domain → the fixtures its rules can actually answer about.

    Not a filename match: fixtures are named for the shape of the resource
    (`site-sharing-anyone-default-anyone`), never for a rule, so searching them
    for rule ids finds nothing and reports every domain as having no fixtures.
    The exact question is which fixture a domain's rules return an answer for,
    and the engine is right here, so it is asked rather than guessed.
    """
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(TESTS))
    from conftest import evidence, rule  # noqa: PLC0415
    from m365_governance.engine import evaluate_rule  # noqa: PLC0415

    out = defaultdict(set)
    names = sorted(p.stem for p in (DATA / "fixtures").rglob("*.json"))
    for domain, ids in on_disk.items():
        loaded = [rule(rid) for rid in ids]
        for name in names:
            try:
                document = evidence(name)
            except Exception:  # a fixture the loader rejects is not coverage
                continue
            for one in loaded:
                try:
                    if evaluate_rule(one, document).outcome.is_answer:
                        out[domain].add(name)
                        break
                except Exception:
                    continue
    return {d: sorted(v) for d, v in out.items()}


def site_surfaces() -> dict:
    """Guide, Knowledge, Analysis and Compass, from the site checkout.

    Returns a dict whose `state` is `observed` or `missing`, never a silent
    zero. A surface nobody looked at is not a surface that is empty.
    """
    if not SITE.is_dir():
        return {"state": "missing", "detail": f"site checkout not found at {SITE}"}

    # All four surfaces are read from the Knowledge frontmatter, because that
    # is where the product's relations actually live and where the site's own
    # check validates them: `next_guide` against written chapters, `next_blog`
    # against published posts, `next_compass` as yes or no.
    #
    # Searching the Guide and the Compass for rule ids was wrong twice over.
    # It missed chapter 13, which interprets two sharing facts at length and
    # names no id, because the Guide links through the graph and not through
    # citations. And it credited domains for ids appearing in a handover, an
    # audit and the search index, which are not chapters and not findings.
    # **A false positive closes a row that is open**, which is worse than the
    # gap it hides: the queue stops asking for work that is genuinely missing.
    # Requiring an id in a chapter would also have forced rule numbers into a
    # book to turn a cell green.
    articles = SITE / "src" / "knowledge"
    if not articles.is_dir():
        return {"state": "missing", "detail": f"{articles} does not exist"}

    knowledge, guide, analysis, compass, by_slug = (
        defaultdict(set),
        defaultdict(set),
        defaultdict(set),
        defaultdict(set),
        defaultdict(set),
    )
    for path in sorted(articles.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        head = text.split("---", 2)[1] if text.startswith("---") else ""

        def listed(key: str, block: str = head) -> list[str]:
            found = re.search(rf"^{key}:\s*\[(.*?)\]\s*$", block, re.M)
            return [v.strip() for v in found.group(1).split(",")] if found else []

        for rid in listed("related_rules"):
            match = RULE_ID.fullmatch(rid)
            if not match:
                continue
            domain, number = match.group(2), match.group(3)
            knowledge[domain].add(number)
            guide[domain].update(f"ch{c}" for c in listed("next_guide"))
            analysis[domain].update(listed("next_blog"))
            by_slug[f"{path.parent.name}/{path.stem}"].add(domain)

    # Compass coverage is the finding's own route to method, in rules.json,
    # not the article's `next_compass` flag. The flag says an article would
    # like to reach the Compass; this says a user-facing finding actually
    # explains itself through that article, which is what the closure
    # criterion asks for.
    findings = SITE / "src" / "tools" / "compass" / "rules.json"
    if findings.is_file():
        for slug in re.findall(
            r'"(sharepoint/[a-z0-9-]+)"', findings.read_text("utf-8")
        ):
            for domain in by_slug.get(slug, ()):
                compass[domain].add(slug)

    found = {
        name: {
            "state": "observed",
            "by_domain": {d: sorted(v) for d, v in hits.items()},
        }
        for name, hits in (
            ("knowledge", knowledge),
            ("guide", guide),
            ("analysis", analysis),
            ("compass", compass),
        )
    }
    return {"state": "observed", "path": str(SITE), "areas": found}


def build() -> dict:
    on_disk = rule_files()
    every = sorted(rid for ids in on_disk.values() for rid in ids)
    slices = collector_modes()
    profiles = profile_rules(every)
    test_hits = ids_by_domain(sorted(TESTS.rglob("*.py")))
    fixture_hits = fixtures_by_domain(on_disk)
    site = site_surfaces()

    domains = {}
    for prefix in sorted(set(on_disk) | set(COVERAGE_DOMAINS)):
        rules = sorted(on_disk.get(prefix, []))
        mine = {r.rsplit("-", 1)[1] for r in rules}

        # A profile belongs to a domain when it selects a rule from it.
        owned = sorted(
            name
            for name, selected in profiles.items()
            if any(r.startswith(f"SPO-{prefix}-") for r in selected)
        )
        modes = sorted(
            {mode for _, (mode, profile) in slices.items() if profile in owned}
        )

        row = {
            "name": SUBJECT_VOCABULARY.get(prefix, "unnamed domain"),
            "rules": rules,
            "profiles": owned,
            "collector_modes": modes,
            # Only the rules that actually exist count. A test or fixture
            # naming a rule that was deleted is a stale reference, not coverage.
            "tests": sorted(mine & test_hits.get(prefix, set())),
            "fixtures": fixture_hits.get(prefix, []),
        }

        if site["state"] == "observed":
            for area, result in site["areas"].items():
                if result["state"] != "observed":
                    row[area] = {"state": "missing", "detail": result["detail"]}
                else:
                    reached = set(result["by_domain"].get(prefix, []))
                    # `knowledge` holds rule numbers, so it is narrowed to the
                    # rules that still exist: an article citing a deleted rule
                    # is a stale reference, not coverage. The other three hold
                    # chapters, post slugs and article names, which have
                    # nothing to intersect with and were being emptied by it.
                    row[area] = sorted(
                        mine & reached if area == "knowledge" else reached
                    )
        else:
            for area in ("knowledge", "guide", "analysis", "compass"):
                row[area] = {"state": "missing", "detail": site["detail"]}

        missing = [
            surface
            for surface in REQUIRED
            if not row.get(surface) or isinstance(row.get(surface), dict)
        ]
        row["missing"] = missing
        row["complete"] = not missing
        domains[prefix] = row

    # The vocabulary ships beside the matrix so the site can validate an
    # article's `domain` against it without keeping a second copy. Each subject
    # says whether an engine coverage obligation exists for it at all, which is
    # what stops a reader seeing `0` where the honest answer is `not defined`.
    subjects = {
        prefix: {
            "name": name,
            "coverage": "defined" if prefix in COVERAGE_DOMAINS else "not defined",
        }
        for prefix, name in sorted(SUBJECT_VOCABULARY.items())
    }

    return {
        "generated_by": "tools/coverage.py",
        "site_repository": site["state"],
        "subjects": subjects,
        "domains": domains,
    }


def percent(part: int, whole: int) -> str:
    return "—" if not whole else f"{round(100 * part / whole)}%"


def as_markdown(matrix: dict) -> str:
    rows = matrix["domains"]
    total = sum(len(r["rules"]) for r in rows.values())

    def cell(value):
        if isinstance(value, dict):
            return "?"
        return str(len(value)) if value else "—"

    lines = [
        "# Product state",
        "",
        "**Generated by `tools/coverage.py`. Do not edit.**",
        "",
        "A matrix somebody maintains by hand starts lying within a week. This",
        "one is derived from the repository, and the release contract fails if",
        "it is out of date.",
        "",
        "A `?` means the surface was not looked at, not that it is empty —",
        "those columns live in the corporate site repository. Set `PH7X_SITE`",
        "to point at it.",
        "",
        "| Domain | Rules | Collector | Profiles | Fixtures | Tests | "
        "Knowledge | Guide | Analysis | Compass | Complete |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for prefix, row in sorted(rows.items(), key=lambda kv: kv[1]["name"]):
        lines.append(
            f"| **{row['name']}** (`{prefix}`) | {cell(row['rules'])} | "
            f"{cell(row['collector_modes'])} | {cell(row['profiles'])} | "
            f"{cell(row['fixtures'])} | {cell(row['tests'])} | "
            f"{cell(row['knowledge'])} | {cell(row['guide'])} | "
            f"{cell(row['analysis'])} | {cell(row['compass'])} | "
            f"{'yes' if row['complete'] else '**no**'} |"
        )

    incomplete = [r for r in rows.values() if not r["complete"]]
    lines += [
        "",
        f"**{total} rules across {len(rows)} domains.** "
        f"{len(rows) - len(incomplete)} complete, {len(incomplete)} not.",
        "",
        "## The Domain Completion Gate",
        "",
        "**A domain that is not complete blocks opening a new one.** Three",
        "half-domains, none of them deep, is the failure mode the strategy",
        "names, and this is the check that makes it arithmetic rather than",
        "judgement.",
        "",
    ]
    if incomplete:
        for row in sorted(incomplete, key=lambda r: r["name"]):
            lines.append(f"- **{row['name']}** — missing {', '.join(row['missing'])}")
    else:
        lines.append("Every domain is complete. A new one may be opened.")

    lines += ["", "## Completeness by surface", ""]
    surfaces = [
        ("Rules", "rules"),
        ("Collectors", "collector_modes"),
        ("Fixtures", "fixtures"),
        ("Tests", "tests"),
        ("Knowledge", "knowledge"),
        ("Guide", "guide"),
        ("Analysis", "analysis"),
        ("Compass", "compass"),
    ]
    for label, key in surfaces:
        have = sum(
            1 for r in rows.values() if r.get(key) and not isinstance(r.get(key), dict)
        )
        unknown = sum(1 for r in rows.values() if isinstance(r.get(key), dict))
        note = f" ({unknown} not looked at)" if unknown else ""
        lines.append(f"- **{label}** {percent(have, len(rows))}{note}")

    lines += [
        "",
        "These are the fraction of **domains** a surface reaches, not a claim",
        "about how good the coverage is inside one. A domain with a single",
        "Knowledge article counts the same as one with six.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if the files on disk are stale"
    )
    args = parser.parse_args()

    matrix = build()
    as_json = json.dumps(matrix, indent=2, sort_keys=True) + "\n"
    as_md = as_markdown(matrix)

    targets = [
        (DOCS / "DOMAIN-COVERAGE.json", as_json),
        (DOCS / "PRODUCT-STATE.md", as_md),
    ]

    if args.check:
        # Without the site checkout, the site-derived columns cannot be
        # verified, and comparing against them would fail every machine that
        # does not happen to have both repositories side by side. The
        # comparison narrows to what this run could measure, and says out loud
        # what it did not check. A green tick quietly covering less than it
        # claims is the same lie as a stale matrix.
        if matrix["site_repository"] != "observed":
            stored = json.loads(
                (DOCS / "DOMAIN-COVERAGE.json").read_text(encoding="utf-8")
            )
            keys = [k for k in REQUIRED if k not in SITE_COLUMNS]
            for prefix, row in matrix["domains"].items():
                was = stored["domains"].get(prefix, {})
                if any(row.get(k) != was.get(k) for k in keys):
                    print(f"  ✗ stale: {prefix} — run tools/coverage.py")
                    return 1
            print(
                f"  ✓ {len(matrix['domains'])} domains current; "
                f"{', '.join(SITE_COLUMNS)} not checked (no site checkout)"
            )
            return 0

        stale = [
            path.name
            for path, wanted in targets
            if not path.is_file() or path.read_text(encoding="utf-8") != wanted
        ]
        if stale:
            print(f"  ✗ stale: {', '.join(stale)} — run tools/coverage.py")
            return 1
        print(f"  ✓ {len(matrix['domains'])} domains, matrix current")
        return 0

    for path, wanted in targets:
        path.write_text(wanted, encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
