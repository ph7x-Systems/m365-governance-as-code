"""The target, written down once.

Ten slices against one tenant were ten commands, each repeating the application
registration and an address. What is tested here is not that a file can be
read: it is that the file never wins against a person, never carries a
credential, and never arrives without saying where it came from.
"""

from __future__ import annotations

import pytest

from m365_governance import project
from m365_governance.cli import main
from m365_governance.loader import DocumentError

WRITTEN = """
[target]
tenant_url = "https://contoso-admin.sharepoint.com"
site_url = "https://contoso.sharepoint.com/sites/finance"

[identity]
client_id = "c0ffee00-0000-4000-8000-000000000001"
"""


def _project(tmp_path, text: str = WRITTEN):
    path = tmp_path / project.NAME
    path.write_text(text, encoding="utf-8")
    return path


def test_it_fills_what_the_command_line_did_not_say(tmp_path):
    class Args:
        client_id = None
        tenant_url = None
        site_url = None

    args = Args()
    filled = project.load(_project(tmp_path)).apply(args)

    assert args.client_id == "c0ffee00-0000-4000-8000-000000000001"
    assert args.tenant_url == "https://contoso-admin.sharepoint.com"
    assert filled == ["client_id", "site_url", "tenant_url"]


def test_the_command_line_always_wins(tmp_path):
    """A file that could override an argument somebody typed would make one
    command mean two things in two directories."""

    class Args:
        client_id = "99999999-8888-7777-6666-555555555555"
        tenant_url = None
        site_url = None

    args = Args()
    filled = project.load(_project(tmp_path)).apply(args)

    assert args.client_id == "99999999-8888-7777-6666-555555555555"
    assert "client_id" not in filled


SECRETS = [
    ('[identity]\ncertificate_password = "hunter2"', "certificate_password"),
    ('[identity]\nclient_secret = "hunter2"', "client_secret"),
    ('[identity]\npassword = "hunter2"', "password"),
]


@pytest.mark.parametrize("text,key", SECRETS, ids=[k for _, k in SECRETS])
def test_a_credential_is_refused_rather_than_ignored(tmp_path, text, key):
    """Ignoring it would leave the secret in a file somebody commits, while the
    run carried on and looked correct."""
    with pytest.raises(DocumentError) as refused:
        project.load(_project(tmp_path, text))

    assert key in str(refused.value)
    assert "certificate_password_env" in str(refused.value)


def test_a_setting_that_does_not_exist_is_named(tmp_path):
    """A misspelled key that was ignored would leave a run using a default
    while the file on disk said otherwise."""
    with pytest.raises(DocumentError) as refused:
        project.load(_project(tmp_path, '[identity]\nclientid = "x"'))

    assert "clientid" in str(refused.value)


def test_a_section_that_does_not_exist_is_named(tmp_path):
    with pytest.raises(DocumentError) as refused:
        project.load(_project(tmp_path, '[tenant]\nurl = "x"'))

    assert "[tenant]" in str(refused.value)


def test_it_is_found_from_a_subdirectory(tmp_path):
    """A repository has one target and many directories."""
    _project(tmp_path)
    deep = tmp_path / "evidence" / "august"
    deep.mkdir(parents=True)

    assert project.find(deep) == tmp_path / project.NAME


def test_no_file_anywhere_is_not_an_error(tmp_path):
    assert project.find(tmp_path) is None


# ---------------------------------------------------------------------------
# Through the command line


def test_connect_reads_the_identity_from_the_file(tmp_path, monkeypatch, capsys):
    """And says which file, every time.

    A value that arrived from a file the caller did not know about would be the
    ambient configuration this exists instead of.
    """
    _project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "m365_governance.collecting.preflight", lambda: ["stopped before the tenant"]
    )

    code = main(["connect"])
    err = capsys.readouterr().err

    assert code == 2
    assert project.NAME in err
    assert "client_id" in err


def test_without_a_file_the_identity_is_still_required(tmp_path, monkeypatch, capsys):
    """The requirement did not go away when the parser stopped enforcing it."""
    monkeypatch.chdir(tmp_path)

    code = main(["connect", "--tenant-url", "https://contoso-admin.sharepoint.com"])
    err = capsys.readouterr().err

    assert code == 2
    assert "no --client-id" in err
    assert project.NAME in err
    assert "Traceback" not in err


def test_the_file_that_was_read_is_named_whatever_the_format_is_called(
    tmp_path, monkeypatch, capsys
):
    """It was conditional on `--format text`, and `run` has no such format.

    So `run` read a project file found in a parent directory and said nothing
    about it — the ambient configuration this file exists instead of, restored
    by a condition that assumed every command names its formats the same way.
    Observed by walking the journey on 2026-08-21.

    stderr was always the right stream: a consumer parsing a document on stdout
    is unaffected by a line that never goes there.
    """
    _project(tmp_path)
    deep = tmp_path / "evidence" / "august"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    main(["run", "--dry-run"])
    err = capsys.readouterr().err

    assert project.NAME in err
    assert "client_id" in err
