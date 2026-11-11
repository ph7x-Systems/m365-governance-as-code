"""The golden path: prepare, then one command to a report.

What is tested is not that a plan can be built. It is that a slice the target
cannot reach is REPORTED rather than dropped, that nothing is registered on
anybody's behalf, and that a project file somebody wrote is not overwritten
because a command was run twice.
"""

from __future__ import annotations

from m365_governance import project, running
from m365_governance.cli import main

GUID = "c0ffee00-0000-4000-8000-000000000001"
TENANT = "https://contoso-admin.sharepoint.com"
SITE = "https://contoso.sharepoint.com/sites/finance"


def run(capsys, *argv) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ---------------------------------------------------------------------------
# The plan


def test_a_site_target_cannot_reach_what_needs_the_organisation():
    steps = running.plan(site_url=SITE, tenant_url=None, has_graph_token=False)
    verdicts = {step.name: step.planned for step in steps}

    assert verdicts["owners"] is running.Planned.ATTEMPT
    assert verdicts["tenant-sharing"] is running.Planned.NO_TENANT
    assert verdicts["sites"] is running.Planned.NO_TENANT


def test_a_tenant_target_cannot_reach_what_needs_one_site():
    steps = running.plan(site_url=None, tenant_url=TENANT, has_graph_token=False)
    verdicts = {step.name: step.planned for step in steps}

    assert verdicts["sites"] is running.Planned.ATTEMPT
    assert verdicts["owners"] is running.Planned.NO_SITE


def test_graph_is_not_attempted_without_a_token():
    """This engine never acquires one, so its absence is a fact about the run."""
    steps = running.plan(site_url=SITE, tenant_url=TENANT, has_graph_token=False)
    verdicts = {step.name: step.planned for step in steps}

    assert verdicts["conditional-access"] is running.Planned.NO_TOKEN


def test_every_slice_appears_in_the_plan_with_a_verdict():
    """The unattempted ones are the point.

    A run that quietly skipped half its slices would produce a report that
    looks complete to the only person who could tell that it is not.
    """
    from m365_governance.collecting import SLICES

    steps = running.plan(site_url=None, tenant_url=None, has_graph_token=False)

    assert {step.name for step in steps} == set(SLICES)
    assert all(step.because for step in steps)


def test_what_was_not_attempted_is_written_where_a_person_reads_it():
    steps = running.plan(site_url=SITE, tenant_url=None, has_graph_token=False)
    said = running.describe(steps)

    assert "not run  tenant-sharing" in said
    assert "no admin address is configured" in said
    assert "is not a resource that is not" in said


# ---------------------------------------------------------------------------
# setup


def test_setup_names_the_command_that_produces_an_application(
    capsys, tmp_path, monkeypatch
):
    """The step that stops people, and nothing in this product named it.

    The only instruction anywhere was "register an Entra ID app, or use one
    your tenant already has": the hardest step described as an aside.
    """
    monkeypatch.chdir(tmp_path)

    code, out, _err = run(capsys, "setup")

    assert code == 0
    assert "Register-PnPEntraIDAppForInteractiveLogin" in out
    assert not (tmp_path / project.NAME).exists()


def test_the_registration_command_pastes_into_powershell_and_names_its_permissions():
    """It was printed over lines ending in a backslash, which PowerShell does
    not continue: the first line ran alone and every parameter failed as a
    command of its own. And with no permissions named, PnP asks for write
    access to groups, users and the term store, which nothing here uses."""
    from m365_governance.cli import REGISTRATION

    assert "\n" not in REGISTRATION and "\\" not in REGISTRATION
    assert "-SharePointDelegatePermissions AllSites.FullControl" in REGISTRATION
    assert "-GraphDelegatePermissions User.Read" in REGISTRATION
    assert "ReadWrite" not in REGISTRATION


def test_a_missing_identity_says_how_to_obtain_one(capsys, tmp_path, monkeypatch):
    """Naming what is missing is half a diagnosis; the first-run contract asks
    every step that needs something the user does not have to say how to
    obtain it."""
    monkeypatch.chdir(tmp_path)

    code, _out, err = run(capsys, "connect", "--tenant-url", TENANT, "--dry-run")

    assert code == 2
    assert "m365g engine setup" in err


def test_the_assessment_diff_names_a_resource_the_way_a_reader_does(capsys, tmp_path):
    """`diff` printed each resource as a Python dictionary. The comparison
    document keeps the whole record; the report names its type and its id."""
    from importlib.resources import files

    fixtures = files("m365_governance") / "data" / "fixtures" / "sharepoint"
    for name, out in (
        ("list-within-limit", "before.json"),
        ("list-over-limit", "after.json"),
    ):
        code, _out, err = run(
            capsys,
            "assess",
            "--evidence",
            str(fixtures / f"{name}.json"),
            "--created-at",
            "2026-08-08T09:00:00Z",
            "--out",
            str(tmp_path / out),
        )
        assert code == 0, err

    _code, out, _err = run(
        capsys, "diff", str(tmp_path / "before.json"), str(tmp_path / "after.json")
    )

    assert "{'" not in out
    assert "on list `contoso,list,archive`" in out


def test_setup_writes_a_project_file_and_never_a_secret(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code, _out, _err = run(
        capsys,
        "setup",
        "--client-id",
        GUID,
        "--tenant-url",
        TENANT,
        "--certificate-password-env",
        "M365_GOVERNANCE_CERT_PASSWORD",
    )
    written = (tmp_path / project.NAME).read_text(encoding="utf-8")

    assert code == 0
    assert GUID in written
    assert "NO SECRET BELONGS IN THIS FILE" in written
    assert 'certificate_password_env = "M365_GOVERNANCE_CERT_PASSWORD"' in written
    # And what it wrote is what the loader accepts. A setup that produced a
    # file its own reader refuses would be discovered by a user, not by us.
    assert project.load(tmp_path / project.NAME).values["client_id"] == GUID


def test_setup_does_not_overwrite_a_target_somebody_chose(
    capsys, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / project.NAME).write_text("# mine\n", encoding="utf-8")

    code, _out, err = run(capsys, "setup", "--client-id", GUID, "--tenant-url", TENANT)

    assert code == 2
    assert "--force" in err
    assert (tmp_path / project.NAME).read_text(encoding="utf-8") == "# mine\n"


def test_setup_refuses_a_file_with_no_target(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code, _out, err = run(capsys, "setup", "--client-id", GUID)

    assert code == 2
    assert "names nothing to assess" in err


def test_setup_refuses_an_identifier_that_cannot_be_a_registration(
    capsys, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    code, _out, err = run(
        capsys, "setup", "--client-id", "nope", "--tenant-url", TENANT
    )

    assert code == 2
    assert "not an application registration" in err


# ---------------------------------------------------------------------------
# run


def test_run_plans_from_the_project_file_and_reaches_nothing(
    capsys, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / project.NAME).write_text(
        f'[target]\ntenant_url = "{TENANT}"\n\n[identity]\nclient_id = "{GUID}"\n',
        encoding="utf-8",
    )

    code, _out, err = run(capsys, "run", "--dry-run")

    assert code == 0
    assert "sites" in err
    assert "not run  owners" in err


def test_run_refuses_a_target_that_names_nothing(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code, _out, err = run(capsys, "run", "--client-id", GUID, "--dry-run")

    assert code == 2
    assert "nothing to collect" in err


def test_run_still_needs_an_identity(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code, _out, err = run(capsys, "run", "--tenant-url", TENANT, "--dry-run")

    assert code == 2
    assert "no --client-id" in err


def test_the_registration_is_the_one_write_and_only_setup_makes_it():
    """D90: the engine's one write to a tenant is the application registration,
    made in `setting_up.register`, only on explicit agreement. No other command
    reaches it, and nothing else in the engine writes."""
    import pathlib

    from m365_governance import cli, setting_up

    text = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    for command in ("run", "connect", "collect", "evaluate", "assess"):
        body = text[text.index(f"def _cmd_{command}(") :]
        body = body[: body.index("\ndef _cmd_", 1)]
        assert "setting_up.register" not in body and "Register-PnP" not in body, command

    package = pathlib.Path(setting_up.__file__).parent
    holders = {
        path.name
        for path in package.rglob("*")
        if path.is_file()
        and path.suffix in (".py", ".ps1", ".psm1")
        and "Register-PnPEntraIDApp"
        in path.read_text(encoding="utf-8", errors="ignore")
    }
    assert holders == {"setting_up.py"}


def test_the_plan_does_not_promise_what_the_machine_cannot_run():
    """Observed on a clean machine, 2026-08-20.

    With no PowerShell installed, `run --dry-run` printed "Plan: 2 of 11
    collections" and exited 0 — and a dry run is precisely what somebody uses
    to find out whether they are ready. The Graph slice already reported its
    missing token; the ten needing an interpreter said nothing, and `doctor`
    and the preflight both knew.
    """
    steps = running.plan(
        site_url=SITE,
        tenant_url=TENANT,
        has_graph_token=True,
        has_powershell=False,
    )
    verdicts = {step.name: step.planned for step in steps}

    assert verdicts["sites"] is running.Planned.NO_POWERSHELL
    # The Graph slices need no interpreter and are all that is left, which is
    # the honest plan on a machine with no PowerShell and a token. There are two
    # now, and the assertion is a list rather than a name for that reason: the
    # day a third ships, this is where the plan says so.
    assert [step.name for step in running.attempted(steps)] == [
        "conditional-access",
        "tenant-governance",
    ]
    assert "doctor" in running.describe(steps)


def test_only_limits_the_plan_and_shows_what_was_left_out():
    """`--only` names the collections to attempt; the rest stay in the plan."""
    from m365_governance import running

    steps = running.plan(
        site_url="https://contoso.sharepoint.com/sites/a",
        tenant_url="https://contoso-admin.sharepoint.com",
        has_graph_token=True,
        only={"sites", "owners"},
    )
    by_name = {step.slice.name: step.planned for step in steps}
    assert len(by_name) == len(running.SLICES), "a collection left the plan"
    assert [n for n, p in by_name.items() if p is running.Planned.ATTEMPT] == [
        "owners",
        "sites",
    ]
    left = {n for n, p in by_name.items() if p is running.Planned.LEFT_OUT}
    assert left == set(running.SLICES) - {"sites", "owners"}
    assert "--only" in running.BECAUSE[running.Planned.LEFT_OUT]


def test_only_refuses_a_name_that_is_not_a_collection(capsys, monkeypatch, tmp_path):
    import m365_governance.cli as cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("M365G_HOME", str(tmp_path / "home"))
    code = cli.main(
        [
            "run",
            "--client-id",
            "3f6c1d9a-7b24-4e58-9a01-c2d47be8f615",
            "--tenant-url",
            "https://contoso-admin.sharepoint.com",
            "--only",
            "sites,nonsense",
            "--dry-run",
        ]
    )
    err = capsys.readouterr().err
    assert code == 2 and "nonsense" in err and "tenant-sharing" in err
