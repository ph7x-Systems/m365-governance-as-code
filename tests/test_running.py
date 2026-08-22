"""The golden path: prepare, then one command to a report.

What is tested is not that a plan can be built. It is that a slice the target
cannot reach is REPORTED rather than dropped, that nothing is registered on
anybody's behalf, and that a project file somebody wrote is not overwritten
because a command was run twice.
"""

from __future__ import annotations

import pytest

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


@pytest.mark.parametrize("command", ["setup", "run"])
def test_neither_command_registers_anything(command):
    """This engine reads and acquires nothing.

    A read-only product that quietly wrote to a directory during setup would
    have a write path after all, and the gate that proves the collector never
    mutates a tenant does not read this file.
    """
    from m365_governance import cli

    source = cli.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()

    body = text[text.index(f"def _cmd_{command}(") :]
    body = body[: body.index("\ndef _cmd_", 1)]
    for forbidden in ("New-", "Register-PnPEntraIDApp", "Set-Pnp", "Remove-"):
        assert f"{forbidden}(" not in body


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
    # The Graph slice needs no interpreter and is the only one left, which is
    # the honest plan on a machine with no PowerShell and a token.
    assert [step.name for step in running.attempted(steps)] == ["conditional-access"]
    assert "doctor" in running.describe(steps)
