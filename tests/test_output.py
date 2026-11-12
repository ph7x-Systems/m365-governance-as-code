"""`--output` says how a result is shown, and a view is never the evidence.

docs/CLI.md states the rules. The collector is replaced, where the suite's
guard says to replace it, by one that writes a packaged fixture as though it
had read a site: no process starts and nothing can authenticate.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import m365_governance.cli as cli
from m365_governance import collecting, presenting, resources

CLIENT = "3f6c1d9a-7b24-4e58-9a01-c2d47be8f615"
TENANT = "https://contoso-admin.sharepoint.com"
SITE = "https://contoso.sharepoint.com/sites/Marketing"
FIXTURE = resources.packaged("fixtures") / "sharepoint" / "site-one-owner.json"


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    (tmp_path / "bin").mkdir()
    present = tmp_path / "bin" / "pwsh"
    present.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    present.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("M365G_HOME", str(tmp_path / "record"))
    monkeypatch.delenv("PH7X_ENGINE", raising=False)
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    seen = []

    def collector(argv, on_progress=None):
        argv = [str(a) for a in argv]
        seen.append(argv)
        where = Path(argv[argv.index("-OutputPath") + 1])
        where.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURE, where / "site-marketing.json")
        return 0, "", "", False

    monkeypatch.setattr(collecting, "_run", collector)

    def call(*argv):
        capsys.readouterr()
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else 1
        said = capsys.readouterr()
        return SimpleNamespace(returncode=code, stdout=said.out, stderr=said.err)

    call.seen = seen
    call.root = tmp_path
    return call


OWNERS = ("spo", "owner", "list", "--client-id", CLIENT, "--site-url", SITE)


def test_a_read_answers_in_the_terminal_as_text_by_default(run):
    out = run(*OWNERS)
    assert out.returncode == 0, out.stderr
    assert "Marketing" in out.stdout and SITE in out.stdout
    assert "owners" in out.stdout and "effective_count=1" in out.stdout
    assert "{raw" not in out.stdout, "a fact was printed as its own keys"
    assert "evidence NOT kept" in out.stderr and "--evidence-out" in out.stderr


def test_the_json_view_is_the_evidence_documents_and_nothing_else_on_stdout(run):
    out = run(*OWNERS, "--output", "json")
    documents = json.loads(out.stdout)
    assert documents == [json.loads(FIXTURE.read_text(encoding="utf-8"))]
    assert documents[0]["provenance"]["collector"], (
        "provenance was dropped from the view"
    )


def test_csv_has_stable_leading_headers_and_one_row_per_resource(run):
    out = run(*OWNERS, "--output", "csv")
    rows = list(csv.reader(io.StringIO(out.stdout)))
    assert tuple(rows[0][: len(presenting.LEADING)]) == presenting.LEADING
    assert rows[0][len(presenting.LEADING) :] == ["owners"]
    assert len(rows) == 2 and rows[1][1] == "Marketing"


def test_markdown_is_a_table(run):
    out = run(*OWNERS, "--output", "md")
    lines = out.stdout.splitlines()
    assert lines[0].startswith("| resource_type | name | url |")
    assert set(lines[1]) <= set("|-") and "Marketing" in lines[2]


def test_evidence_is_kept_only_where_evidence_out_says(run, tmp_path):
    kept = tmp_path / "kept"
    out = run(*OWNERS, "--output", "json", "--evidence-out", kept)
    assert out.returncode == 0
    written = [p for p in kept.rglob("*.json") if collecting.is_evidence(p)]
    assert len(written) == 1
    assert json.loads(out.stdout) == [json.loads(written[0].read_text())]
    assert f"evidence kept in {kept}" in out.stderr

    run(*OWNERS)
    temporary = Path(run.seen[-1][run.seen[-1].index("-OutputPath") + 1])
    assert not temporary.exists(), "a view left tenant evidence behind"


def test_the_earlier_spelling_writes_evidence_and_prints_the_earlier_report(
    run, tmp_path
):
    where = tmp_path / "evidence"
    out = run(
        "collect",
        "owners",
        "--client-id",
        CLIENT,
        "--site-url",
        SITE,
        "--output",
        where,
    )
    assert out.returncode == 0
    assert "evidence documents in" in out.stdout and "Evaluate with:" in out.stdout
    assert "NOT kept" not in out.stderr
    assert any(collecting.is_evidence(p) for p in where.rglob("*.json"))


def test_a_directory_given_twice_is_a_refusal(run, tmp_path):
    out = run(*OWNERS, "--output", tmp_path / "a", "--evidence-out", tmp_path / "b")
    assert out.returncode == 2 and "directory twice" in out.stderr
    assert run.seen == []


def test_a_dry_run_of_a_view_reaches_nothing(run):
    out = run(*OWNERS, "--dry-run")
    assert out.returncode == 0 and "-Mode SiteOwners" in out.stdout
    assert run.seen == []


def test_output_is_the_format_on_commands_that_called_it_format(run, capsys):
    as_output = run("capabilities", "--output", "json").stdout
    as_format = run("capabilities", "--format", "json").stdout
    assert as_output == as_format and json.loads(as_output)
    assert run("rule", "list").returncode == 0
    status = run("status", "--output", "json")
    assert json.loads(status.stdout)["logged_in"] is False
    listed = run("connection", "list", "--output", "json")
    assert json.loads(listed.stdout) == []


def test_md_is_markdown_where_the_command_calls_it_that(tmp_path):
    parser = cli._build_parser()
    assert cli._uniform_output(parser, ["report", "r.json", "--output", "md"]) == [
        "report", "r.json", "--format", "markdown",
    ]  # fmt: skip
    assert cli._uniform_output(parser, ["diff", "a", "b", "--output=json"]) == [
        "diff", "a", "b", "--format", "json",
    ]  # fmt: skip


def test_on_run_output_is_still_the_evidence_directory_unless_it_is_a_format(tmp_path):
    parser = cli._build_parser()
    same = ["run", "--project", "p.toml", "--output", "evidence", "--format", "json"]
    assert cli._uniform_output(parser, same) == same
    assert cli._uniform_output(parser, ["run", "--output", "json"]) == [
        "run", "--format", "json",
    ]  # fmt: skip
    both = ["run", "--evidence-out", "e", "--output", "md"]
    assert cli._uniform_output(parser, both) == [
        "run", "--output", "e", "--format", "markdown",
    ]  # fmt: skip


def test_a_format_given_twice_is_a_refusal(run):
    out = run("capabilities", "--format", "json", "--output", "text")
    assert out.returncode == 2 and "format twice" in out.stderr


def test_a_view_shows_the_collectors_words_and_concludes_nothing():
    document = {
        "resource": {
            "type": "site",
            "display_name": "A",
            "native_id": "a",
            "url": None,
        },
        "provenance": {"collected_at": "2026-11-11T00:00:00Z"},
        "coverage": {"completed": [], "unavailable": {"owners": {"reason": "denied"}}},
        "facts": {
            "sharing": {
                "state": "unknown",
                "value": None,
                "links": [1, 2],
                "by": {"x": 1},
            },
            "count": 3,
        },
    }
    assert presenting.fact(document["facts"]["sharing"]) == (
        "[unknown]; by: {x}; links: 2 entries"
    )
    assert presenting.fact({"state": "observed", "value": True, "raw": {}}) == "true"
    nested = {
        "state": "observed",
        "direct_count": {"state": "observed", "value": 2, "raw": {}},
        "group_count": {"state": "missing", "detail": "not read"},
    }
    assert presenting.fact(nested) == "direct_count=2; group_count=[missing]"
    assert presenting.fact({"state": "observed", "value": ["a", "b"]}) == "a, b"
    assert presenting.fact({"state": "observed", "value": [{"a": 1}]}) == "1 entries"
    text = presenting.render([document], "text")
    assert "UNAVAILABLE: denied" in text and "unknown" in text
    headers, rows = presenting.table([document])
    assert headers[-2:] == ["count", "sharing"] and rows[0][7] == "owners"
    assert presenting.render([], "text") == "Nothing was read.\n"
    for word in ("pass", "fail", "compliant", "score", "%"):
        assert word not in text.lower()
    with pytest.raises(ValueError):
        presenting.render([document], "yaml")


def test_output_is_in_the_help_of_every_command_that_has_a_format():
    import argparse

    parser = cli._build_parser()
    subs = argparse._SubParsersAction
    action = next(a for a in parser._actions if isinstance(a, subs))
    with_format = [
        name
        for name, sub in action.choices.items()
        if any("--format" in a.option_strings for a in sub._actions)
    ]
    assert {"connect", "capabilities", "report", "diff", "status", "login"} <= set(
        with_format
    )
    for name in with_format:
        assert "--output" in action.choices[name].format_help(), name


# --- narrowing and ordering a view --------------------------------------------


def _doc(name, **facts):
    return {
        "resource": {"type": "site", "display_name": name, "native_id": name},
        "provenance": {"collected_at": "2026-11-12T10:00:00Z"},
        "coverage": {"completed": [], "unavailable": {}},
        "facts": {
            "sharing": {
                key: (
                    {"state": "observed", "value": value}
                    if not isinstance(value, dict)
                    else value
                )
                for key, value in facts.items()
            }
        },
    }


DOCS = [
    _doc("b", capability="Disabled", guests=10),
    _doc("a", capability="ExternalUserSharingOnly", guests=2),
    _doc("c", capability={"state": "permission-denied", "detail": "no"}, guests=1),
]


def _names(documents):
    return [d["resource"]["display_name"] for d in documents]


def test_a_filter_matches_what_the_view_prints_and_returns_whole_documents():
    shown = presenting.select(DOCS, ["sharing.capability=disabled"])
    assert _names(shown) == ["b"]
    assert shown[0] is DOCS[0], "a filtered document was altered or copied"
    both = presenting.select(DOCS, ["sharing.capability=Disabled", "name=b"])
    assert _names(both) == ["b"]
    assert presenting.select(DOCS, ["sharing.capability=Nothing"]) == []


def test_a_value_never_matches_something_that_was_not_observed():
    """THE COUNTER-CHECK. A refused site must not be found by asking for a
    value, and must be findable by asking for the refusal."""
    for value in ("Disabled", "", "null", "permission-denied"):
        assert "c" not in _names(
            presenting.select(DOCS, [f"sharing.capability={value}"])
        )
    refused = presenting.select(DOCS, ["sharing.capability=[permission-denied]"])
    assert _names(refused) == ["c"]


def test_a_column_nobody_has_is_refused_and_not_an_empty_view():
    with pytest.raises(presenting.NoSuchColumn, match="sharing.capability"):
        presenting.select(DOCS, ["sharing.capabilty=Disabled"])
    with pytest.raises(presenting.NoSuchColumn):
        presenting.select(DOCS, sort="nothing")
    with pytest.raises(ValueError, match="column=value"):
        presenting.select(DOCS, ["sharing.capability"])


def test_numbers_sort_as_numbers_and_a_state_among_them_does_not_break_it():
    assert _names(presenting.select(DOCS, sort="sharing.guests")) == ["c", "a", "b"]
    mixed = [*DOCS, _doc("d", capability="Disabled", guests={"state": "missing"})]
    assert _names(presenting.select(mixed, sort="sharing.guests")) == [
        "c",
        "a",
        "b",
        "d",
    ]
    assert _names(presenting.select(DOCS, sort="name")) == ["a", "b", "c"]


def test_the_command_filters_the_view_and_keeps_every_document(run, tmp_path):
    kept = tmp_path / "kept"
    out = run(*OWNERS, "--where", "name=Nobody", "--evidence-out", str(kept))
    assert out.returncode == 0, out.stderr
    assert "Nothing was read." not in out.stdout
    assert "Nothing that was read matches the filter." in out.stdout
    assert "0 of 1 resources shown" in out.stderr
    assert "holds all of them" in out.stderr
    assert [p for p in kept.rglob("*.json") if "manifest" not in p.name], (
        "the filter removed evidence"
    )
    wrong = run(*OWNERS, "--where", "nmae=Marketing")
    assert wrong.returncode == 2 and "no column is called" in wrong.stderr


def test_a_filtered_view_keeps_byte_identical_evidence(run, tmp_path):
    """THE COUNTER-CHECK. The same read, once with a filter that shows nothing
    and once without, must keep the same documents, byte for byte."""

    def kept(directory, *extra):
        out = run(*OWNERS, *extra, "--evidence-out", str(directory))
        assert out.returncode == 0, out.stderr
        return {
            p.name: json.loads(p.read_text(encoding="utf-8"))
            for p in directory.rglob("*.json")
            if "manifest" not in p.name and "draft" not in p.name
        }

    plain = kept(tmp_path / "plain")
    filtered = kept(tmp_path / "filtered", "--where", "name=Nobody", "--sort", "name")
    assert plain and plain == filtered
