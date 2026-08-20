"""Command line.

Nothing here writes to a tenant. There is no write path in this system:
remediation is text in a rule, addressed to a person.

The commands split into three kinds, and the split is worth keeping:

  read the repository   list-rules, show-rule, doctor
  read the evidence     stats
  produce a result      validate, evaluate, assess, report, diff
  check one that came    verify

Only the third kind reaches a conclusion, and only `evaluate` and `assess`
reach a new one. `report` and `diff` re-read conclusions somebody already
stored, which is why they never need rules: a stored report carries what it
was decided from.

`assess` is `evaluate` plus everything needed to hand the result to somebody
else: the evidence it was decided from, the versions that decided it, and
digests over all of it. `verify` is the other side of that, and it is
deliberately a separate command, because checking something that arrived must
not require the thing that made it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import (
    __version__,
    assessment,
    canonical,
    capabilities,
    collecting,
    comparison,
    composing,
    conditional_access,
    connecting,
    explaining,
    graph,
    migration,
    migration_graph,
    reporting,
    running,
)
from . import doctor as doctor_module
from . import inspect as inspect_module
from . import project as project_file
from .engine import evaluate
from .loader import DocumentError, load_evidence, load_profile, load_rules
from .reporting import (
    many_to_html,
    many_to_json,
    many_to_markdown,
    to_html,
    to_json,
    to_markdown,
)
from .resources import Source, packaged, resolve
from .results import DuplicateResource, Outcome, Run, RunSet
from .validator import validate_evidence_document, validate_rules

#: `None` means "use what shipped with this version". A path means "use
#: exactly this, and nothing else". There is no third option: the packaged set
#: and a supplied set are never merged, because a rule set assembled from both
#: exists only in the memory of whoever typed the command.
#:
#: These were `Path("rules")` and `Path("profiles/default.yaml")`, resolved
#: against the working directory, which is why an installed copy could not
#: find its own rules.
RULES_HELP = (
    "a directory of rule files. Omit to use the rules that shipped with this "
    "version; supplying one replaces them entirely rather than adding to them"
)
PROFILE_HELP = (
    "a profile file. Omit to use the packaged default, which selects every rule"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m365-governance",
        description="Microsoft 365 governance checks that show their work.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser(
        "list-rules", help="every rule, with the kind of claim it makes"
    )
    listing.add_argument("--rules", type=Path, default=None, help=RULES_HELP)

    showing = sub.add_parser(
        "show-rule", help="one rule in full, including what it does not establish"
    )
    showing.add_argument("rule_id", metavar="ID")
    showing.add_argument("--rules", type=Path, default=None, help=RULES_HELP)

    collect = sub.add_parser(
        "collect",
        help="run a collector against a tenant and write evidence. Evaluates nothing",
    )
    collect.add_argument(
        "slice",
        metavar="SLICE",
        choices=sorted(collecting.SLICES),
        help="; ".join(f"{s.name}: {s.describes}" for s in collecting.SLICES.values()),
    )
    collect.add_argument(
        "--client-id",
        help="an Entra ID app registration. Required: PnP.PowerShell has "
        "shipped no application of its own since 2.12.0",
    )
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument(
        "--project",
        type=Path,
        help=(
            f"a project file. Omit to use the nearest {project_file.NAME} "
            f"from here upwards, if there is one"
        ),
    )
    collect.add_argument("--site-url")
    collect.add_argument("--tenant-url", help="https://<tenant>-admin.sharepoint.com")
    collect.add_argument(
        "--device-login",
        action="store_true",
        help="authenticate with a device code, for hosts with no browser",
    )
    collect.add_argument(
        "--tenant-id",
        help="the directory, as an id or a domain. Required with a certificate",
    )
    collect.add_argument(
        "--certificate-path",
        type=Path,
        help=(
            "a PFX holding the application's certificate and private key. "
            "App-only: the run authenticates as the application, not as you"
        ),
    )
    collect.add_argument(
        "--certificate-password-env",
        metavar="NAME",
        help=(
            "the NAME of an environment variable holding the PFX password, "
            "never the password itself: an argument is in the shell history "
            "and in the process list of every user on the machine"
        ),
    )
    collect.add_argument(
        "--count-unique-scopes",
        action="store_true",
        help="permissions only: walk every item of every list",
    )
    collect.add_argument(
        "--dry-run", action="store_true", help="print the command and reach no tenant"
    )

    caps = sub.add_parser(
        "capabilities",
        help="what this engine collects, decides and promises. Reaches no tenant",
    )
    caps.add_argument("--rules", type=Path, default=None, help=RULES_HELP)
    caps.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="json is the published capability-manifest contract",
    )
    caps.add_argument(
        "--questions",
        action="store_true",
        help=(
            "what can be answered about a real tenant, rather than what is "
            "collected: one line per rule, with what decides it and why"
        ),
    )

    connect = sub.add_parser(
        "connect",
        help="reach a tenant and say what was established. Collects nothing",
    )
    connect.add_argument(
        "--client-id",
        help="an Entra ID app registration. Required: PnP.PowerShell has "
        "shipped no application of its own since 2.12.0",
    )
    connect.add_argument("--site-url")
    connect.add_argument(
        "--project",
        type=Path,
        help=(
            f"a project file. Omit to use the nearest {project_file.NAME} "
            f"from here upwards, if there is one"
        ),
    )
    connect.add_argument("--tenant-url", help="https://<tenant>-admin.sharepoint.com")
    connect.add_argument(
        "--dry-run",
        action="store_true",
        help="print the command and reach no tenant. `collect` has had this "
        "since it existed; the command more likely to be run while finding "
        "out how any of this works had no way to be tried",
    )
    connect.add_argument(
        "--device-login",
        action="store_true",
        help="authenticate with a device code, for hosts with no browser",
    )
    connect.add_argument(
        "--tenant-id",
        help="the directory, as an id or a domain. Required with a certificate",
    )
    connect.add_argument(
        "--certificate-path",
        type=Path,
        help=(
            "a PFX holding the application's certificate and private key. "
            "App-only: the run authenticates as the application, not as you"
        ),
    )
    connect.add_argument(
        "--certificate-password-env",
        metavar="NAME",
        help=(
            "the NAME of an environment variable holding the PFX password, "
            "never the password itself: an argument is in the shell history "
            "and in the process list of every user on the machine"
        ),
    )
    connect.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="json for a consumer. Not a contract: a session is not a document",
    )

    setup = sub.add_parser(
        "setup",
        help="prepare a machine and write a project file. Reaches no tenant",
    )
    setup.add_argument("--client-id", help="an Entra ID application registration")
    setup.add_argument("--site-url")
    setup.add_argument("--tenant-url", help="https://<tenant>-admin.sharepoint.com")
    setup.add_argument("--tenant-id")
    setup.add_argument("--certificate-path", type=Path)
    setup.add_argument("--certificate-password-env", metavar="NAME")
    setup.add_argument(
        "--out",
        type=Path,
        default=Path(project_file.NAME),
        help=f"where to write. Default {project_file.NAME} here",
    )
    setup.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing project file",
    )

    run_cmd = sub.add_parser(
        "run",
        help="a configured target to a report, in one command",
    )
    run_cmd.add_argument(
        "--project",
        type=Path,
        help=f"a project file. Omit to use the nearest {project_file.NAME} "
        f"from here upwards, if there is one",
    )
    run_cmd.add_argument("--client-id")
    run_cmd.add_argument("--site-url")
    run_cmd.add_argument("--tenant-url", help="https://<tenant>-admin.sharepoint.com")
    run_cmd.add_argument(
        "--output",
        type=Path,
        default=Path("./evidence"),
        help="where the evidence is written. Kept: it is what the conclusions "
        "were decided from, and a report without it cannot be checked",
    )
    run_cmd.add_argument(
        "--device-login",
        action="store_true",
        help="authenticate with a device code, for hosts with no browser",
    )
    run_cmd.add_argument("--tenant-id")
    run_cmd.add_argument("--certificate-path", type=Path)
    run_cmd.add_argument("--certificate-password-env", metavar="NAME")
    run_cmd.add_argument("--profile", type=Path, default=None, help=PROFILE_HELP)
    run_cmd.add_argument("--rules", type=Path, default=None, help=RULES_HELP)
    run_cmd.add_argument(
        "--format", choices=("markdown", "json", "html"), default="markdown"
    )
    run_cmd.add_argument("--out", type=Path, help="write the report here")
    run_cmd.add_argument(
        "--fail-on",
        choices=("nothing", "fail", "unresolved"),
        default="nothing",
        help="exit 1 on findings. `unresolved` counts unknown and "
        "invalid-evidence alongside fail",
    )
    run_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan and reach no tenant",
    )

    explain = sub.add_parser(
        "explain",
        help="what an outcome means, and what it does not",
    )
    explain.add_argument(
        "outcome",
        metavar="OUTCOME",
        choices=[*explaining.NAMES, "all"],
        help="one of: " + ", ".join(explaining.NAMES) + ", or all",
    )

    doc = sub.add_parser(
        "doctor", help="what is wrong with this installation, before you ask"
    )
    doc.add_argument(
        "--root",
        type=Path,
        default=None,
        help="check content in this directory instead of what is packaged",
    )

    stats = sub.add_parser(
        "stats", help="what a collector managed to see, before evaluating it"
    )
    stats.add_argument("evidence", type=Path)

    validate = sub.add_parser(
        "validate", help="check every rule against the schemas and the invariants"
    )
    validate.add_argument("--rules", type=Path, default=None, help=RULES_HELP)

    evaluate_cmd = sub.add_parser(
        "evaluate", help="run rules against an evidence document"
    )
    evaluate_cmd.add_argument("--rules", type=Path, default=None, help=RULES_HELP)
    evaluate_cmd.add_argument("--evidence", type=Path, required=True)
    evaluate_cmd.add_argument("--profile", type=Path, default=None, help=PROFILE_HELP)
    evaluate_cmd.add_argument(
        "--format", choices=("markdown", "json", "html"), default="markdown"
    )
    evaluate_cmd.add_argument(
        "--fail-on",
        choices=("never", "fail", "unresolved"),
        default="never",
        help=(
            "exit non-zero on findings. 'unresolved' also counts unknown, "
            "invalid-evidence and error"
        ),
    )

    assess = sub.add_parser(
        "assess",
        help="evaluate evidence and write an assessment that can be handed over",
    )
    assess.add_argument("--rules", type=Path, default=None, help=RULES_HELP)
    assess.add_argument("--evidence", type=Path, required=True)
    assess.add_argument("--profile", type=Path, default=None, help=PROFILE_HELP)
    assess.add_argument(
        "--label",
        default=None,
        help=(
            "what to call it. Never used to identify anything: renaming an "
            "assessment does not produce a different one"
        ),
    )
    assess.add_argument(
        "--created-at",
        default=None,
        help=(
            "the timestamp to record, as ISO 8601. Defaults to now. Supply it "
            "to rebuild an assessment byte for byte"
        ),
    )
    assess.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write it. Omit to write to stdout",
    )

    verify = sub.add_parser(
        "verify",
        help="check an assessment that arrived, without the engine that made it",
    )
    verify.add_argument("assessment", type=Path)

    report = sub.add_parser(
        "report", help="re-render a stored report, without evaluating anything"
    )
    report.add_argument("report", type=Path)
    report.add_argument(
        "--format", choices=("markdown", "json", "html"), default="markdown"
    )

    diff = sub.add_parser(
        "diff", help="what changed between two assessments, and what it does not say"
    )
    diff.add_argument("before", type=Path, help="an assessment, from `assess`")
    diff.add_argument("after", type=Path, help="an assessment, from `assess`")
    diff.add_argument("--format", choices=("markdown", "json"), default="markdown")
    diff.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit non-zero when any rule left `pass`",
    )
    reading = sub.add_parser(
        "migration-read",
        help="read one estate at one moment, as the input a verification is built from",
    )
    reading.add_argument("--drive", required=True, help="the drive to enumerate")
    reading.add_argument("--folder", default=None, help="an item id to start at")
    reading.add_argument("--read-id", required=True)
    reading.add_argument(
        "--taken-at",
        required=True,
        help="when this read was taken, ISO 8601. Supplied rather than read "
        "from the clock: it decides which side of the move this is",
    )
    reading.add_argument(
        "--estate", required=True, help="what was read, as you name it"
    )
    reading.add_argument(
        "--with-versions",
        action="store_true",
        help="one extra request PER ITEM. Without it, version history is out "
        "of scope for this read rather than missing from it",
    )
    reading.add_argument(
        "--with-permissions",
        action="store_true",
        help="one extra request PER ITEM; Graph cannot expand permissions on a "
        "collection. Also carries sharing links",
    )
    reading.add_argument("--out", type=Path, help="write the read here")

    moved = sub.add_parser(
        "migration-verify",
        help="what a move actually moved, from a read taken before it and one "
        "taken after",
    )
    moved.add_argument("baseline", type=Path, help="a read taken BEFORE the move")
    moved.add_argument("verification", type=Path, help="a read taken after it")
    moved.add_argument("--kind", default="unstated", help="what kind of move it was")
    moved.add_argument(
        "--performed-by",
        default=None,
        help="what performed the move, so a reader can see it was not us",
    )
    moved.add_argument("--out", type=Path, help="write the record here")
    moved.add_argument(
        "--report-format",
        choices=("markdown", "html"),
        default=None,
        help="defaults to the report file's own suffix, then markdown",
    )
    moved.add_argument(
        "--report",
        type=Path,
        help="write the readable report here. The record is the evidence and "
        "this is the document; both are delivered and neither replaces the "
        "other",
    )

    contracts = sub.add_parser(
        "contracts",
        help="write the contract bundle a consumer vendors: schemas, models, "
        "samples and a manifest",
    )
    contracts.add_argument(
        "--out", required=True, type=Path, help="a directory to write into"
    )

    return parser


# ---------------------------------------------------------------------------
# reading the repository
# ---------------------------------------------------------------------------


def _cmd_list_rules(args) -> int:
    print(inspect_module.list_rules(_rule_source(args).path))
    return 0


def _cmd_show_rule(args) -> int:
    try:
        sys.stdout.write(
            inspect_module.show_rule(_rule_source(args).path, args.rule_id)
        )
    except KeyError as exc:
        print(str(exc).strip('"'), file=sys.stderr)
        return 2
    return 0


def _report_gaps(outcome) -> None:
    """What the documents themselves say they did not read.

    Read from the artefacts rather than from the exit code, and printed
    whenever it is not empty: a partial collection whose gaps are invisible is
    a complete one as far as the reader is concerned.
    """
    for gap in outcome.incomplete:
        print(f"  {gap}")


def _report_manifest(outcome) -> None:
    """Where the account of this collection was written.

    Named on every path, including the failures. A consumer that has to find it
    by convention is a consumer that will one day look in the wrong place and
    conclude the collection was fine.
    """
    if outcome.manifest_path is not None:
        print(f"  the collection is described in {outcome.manifest_path}")


def _cmd_capabilities(args) -> int:
    """What this engine can do, derived from the objects that do it.

    It reaches no tenant and reads no evidence. The JSON form is the published
    contract a consumer projects; the text form is the same document for
    somebody reading rather than parsing.
    """
    # TWO QUESTIONS, AND THEY ARE NOT THE SAME ONE. The manifest answers "what
    # does this product touch"; `--questions` answers "what can it tell me
    # about my tenant", which is the one somebody has. A count of rules is a
    # count of files.
    document = (
        capabilities.questions(args.rules)
        if args.questions
        else capabilities.manifest(args.rules)
    )
    if args.format == "json":
        print(json.dumps(document, indent=2, ensure_ascii=False))
    elif args.questions:
        print(capabilities.describe_questions(document), end="")
    else:
        print(capabilities.describe(document), end="")
    return 0


class AmbiguousIdentity(Exception):
    """The command line names two ways of authenticating, or half of one."""


#: What an Entra ID application registration is: a GUID. Matched here rather
#: than parsed, because nothing in this engine reads inside it.
_APPLICATION_ID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _application_id(value: str) -> None:
    """Refuse an identifier that cannot be an application registration.

    BEFORE ANYTHING LEAVES THIS PROCESS. A value of the wrong shape used to
    start PowerShell, open a browser and fail in the directory, so the product's
    own worst error was diagnosed by Microsoft, in a window, outside the
    terminal a person was looking at. Audited on 2026-08-20 against a live
    tenant: `--client-id not-a-guid` reached `AADSTS700016`.

    This engine already holds the rule -- the cheapest place to stop is before
    the network -- and applied it to authentication modes and to nothing else.

    IT PROVES NOTHING ABOUT THE REGISTRATION. A well-formed GUID may name no
    application at all, and that answer needs the directory. What this removes
    is the class of failure the directory should never have been asked about.
    """
    if not _APPLICATION_ID.match(value.strip()):
        raise AmbiguousIdentity(
            f"--client-id is not an application registration: {value!r}. "
            f"An Entra ID application id is a GUID. If you do not have one, "
            f"register an application in your own tenant: PnP.PowerShell has "
            f"shipped no application of its own since 2.12.0."
        )


def _project(args) -> None:
    """Fill the target and the identity from a project file, and say so.

    BEFORE EVERY OTHER REFUSAL. `--client-id` is no longer required by the
    parser, because a project file may hold it; the requirement did not go
    away, it moved to where both sources have been read. A parser that still
    demanded it would refuse a command the file could have completed.

    Which file was read is printed, always. A value that arrived from a file
    the caller did not know about would be the ambient configuration this
    exists instead of, and a message is the difference between the two.
    """
    named = getattr(args, "project", None)
    path = Path(named) if named else project_file.find()
    if path is None:
        return

    found = project_file.load(path)
    filled = found.apply(args)
    if filled and getattr(args, "format", "text") == "text":
        print(f"{path}: {', '.join(filled)}", file=sys.stderr)


def _authentication(args) -> None:
    """Two modes, and the caller has to have chosen exactly one.

    DELEGATED runs see what one person sees; an APPLICATION with a certificate
    sees what the tenant granted the application. They answer differently, an
    empty result means something different in each, and the evidence records
    which one produced it. A command line that named both, or half of one,
    used to be resolved by whichever branch the script tested first, and the
    run would authenticate as somebody the caller did not choose.

    Refused here rather than in the collector, because the collector reaches a
    tenant and this does not: the cheapest place to stop is before the network.
    """
    client_id = getattr(args, "client_id", None)
    if client_id is None:
        raise AmbiguousIdentity(
            "no --client-id, and no identity in a project file. Every "
            "connection needs an Entra ID application registration: "
            "PnP.PowerShell has shipped no application of its own since "
            f"2.12.0. Write it once in {project_file.NAME} to stop repeating it."
        )
    _application_id(client_id)

    certificate = getattr(args, "certificate_path", None)
    device = getattr(args, "device_login", False)
    tenant_id = getattr(args, "tenant_id", None)
    password_env = getattr(args, "certificate_password_env", None)

    if certificate and device:
        raise AmbiguousIdentity(
            "--certificate-path authenticates the application and "
            "--device-login authenticates a person. Choose one."
        )
    if certificate and not tenant_id:
        raise AmbiguousIdentity(
            "--certificate-path needs --tenant-id: an application-only token "
            "is issued by a directory, and the address alone does not name it."
        )
    if tenant_id and not certificate:
        raise AmbiguousIdentity(
            "--tenant-id is for the certificate flow. A delegated sign-in "
            "takes the directory from the address and the person signing in."
        )
    if password_env and not certificate:
        raise AmbiguousIdentity(
            "--certificate-password-env is for the certificate flow, and "
            "there is no certificate here."
        )
    if password_env and not os.environ.get(password_env):
        raise AmbiguousIdentity(
            f"--certificate-password-env names {password_env}, and that "
            f"variable is empty or unset in this shell. The name is passed, "
            f"never the value."
        )
    if certificate and not Path(certificate).exists():
        raise AmbiguousIdentity(f"--certificate-path does not exist: {certificate}")


def _cmd_collect(args) -> int:
    # BEFORE ANYTHING REACHES A TENANT. Which identity a run authenticates as
    # decides what an empty result means, and a command line naming two of
    # them, or half of one, used to be settled by whichever branch the script
    # tested first.
    try:
        _project(args)
        _authentication(args)
    except AmbiguousIdentity as refusal:
        print(f"refusing to run: {refusal}", file=sys.stderr)
        return 2

    chosen = collecting.SLICES[args.slice]

    # PowerShell is what the SharePoint collector runs in, and a Graph slice
    # needs none of it. Asking for it anyway would refuse a collection this
    # installation is perfectly able to perform.
    if chosen.source == "powershell":
        for problem in collecting.preflight():
            print(problem, file=sys.stderr)
            return 2

    if chosen.needs_site and not args.site_url:
        print(f"collect {args.slice} needs --site-url", file=sys.stderr)
        return 2
    # THE KIND OF PATH IS PART OF THE CONTRACT, and it was not checked. A
    # slice that reads many resources writes a document per resource into a
    # directory; a slice that reads one writes a file. Passing the wrong kind
    # surfaced as `Clear-Content is only supported on files.` four seconds into
    # a run, which is an internal error from another language and tells the
    # reader nothing about what they did.
    if chosen.writes_many and args.output.is_file():
        print(
            f"collect {args.slice} reads many resources and writes one document "
            f"per resource, so --output is a directory. {args.output} is a file.",
            file=sys.stderr,
        )
        return 2
    if not chosen.writes_many and args.output.is_dir():
        print(
            f"collect {args.slice} reads one resource and writes one document, "
            f"so --output is a file. {args.output} is a directory: give it a "
            f"path such as {args.output / (args.slice + '.json')}.",
            file=sys.stderr,
        )
        return 2

    if chosen.needs_tenant and not args.tenant_url:
        print(
            f"collect {args.slice} needs --tenant-url, the admin centre. "
            + (
                "The token says which directory the session opened in; the "
                "address is what lets this evidence and SharePoint evidence be "
                "one tenant in an assessment."
                if chosen.source == "graph"
                else "Sharing settings are a tenant property about a site."
            ),
            file=sys.stderr,
        )
        return 2

    if chosen.source == "graph":
        return _collect_from_graph(args, chosen)

    # Printed as it arrives. `collect sites` against a large tenant used to
    # print nothing for however long it took and then print everything, so the
    # only thing distinguishing a working collection from a hung one was the
    # patience of the person waiting.
    def report(line: str) -> None:
        print(line, flush=True)

    outcome = collecting.run_slice(
        args.slice,
        client_id=args.client_id,
        output=args.output,
        site_url=args.site_url,
        tenant_url=args.tenant_url,
        device_login=args.device_login,
        tenant_id=args.tenant_id,
        certificate_path=args.certificate_path,
        certificate_password_env=args.certificate_password_env,
        count_unique_scopes=args.count_unique_scopes,
        dry_run=args.dry_run,
        on_progress=None if args.dry_run else report,
    )

    if args.dry_run:
        print(outcome.stdout)
        return 0

    return _report_collection(args, chosen, outcome)


def _collect_from_graph(args, chosen) -> int:
    """The Graph half of `collect`, which acquires nothing.

    The token comes from the environment because this engine never obtains one.
    A missing token is a refusal with the command that produces it, not a stack
    trace and not an attempt to sign somebody in.

    The project file is not read again here: `collect` resolved it before
    choosing a slice, and reading it twice would report the same file twice to
    somebody who has already been told.
    """
    try:
        _authentication(args)
    except AmbiguousIdentity as refusal:
        print(f"refusing to run: {refusal}", file=sys.stderr)
        return 2

    token = os.environ.get(conditional_access.TOKEN_VARIABLE, "")

    if args.dry_run:
        paths = [
            *conditional_access.AREAS.values(),
            *conditional_access.SINGLE.values(),
        ]
        held = "set" if token else "not set"
        print(
            f"collect {args.slice} would read, in one session:\n"
            + "\n".join(f"  GET {path}" for path in paths)
            + f"\n\nwith the token in {conditional_access.TOKEN_VARIABLE}, "
            f"which is {held}."
        )
        return 0

    if not token:
        print(
            f"collect {args.slice} reads Microsoft Graph and never acquires a "
            f"token: it spends one you already hold. Put it in "
            f"{conditional_access.TOKEN_VARIABLE}.\n\n{conditional_access.HOW}",
            file=sys.stderr,
        )
        return 2

    def report(line: str) -> None:
        print(line, flush=True)

    outcome = conditional_access.run(
        token=token,
        output=args.output,
        tenant_url=args.tenant_url,
        client_id=args.client_id,
        on_progress=report,
    )
    if outcome.stderr:
        print(outcome.stderr, file=sys.stderr)
    return _report_collection(args, chosen, outcome)


def _report_collection(args, chosen, outcome) -> int:
    """What a collection produced, in the vocabulary of its four states.

    Shared by both collectors on purpose. The state, the gaps, the manifest and
    the evaluation line are facts about a collection rather than about the
    process that performed it, and a second copy here would be the second place
    where `partial` quietly starts meaning something else.
    """
    state = outcome.state

    if state is collecting.State.FAILED:
        print(
            f"\ncollection failed after {outcome.seconds:.1f}s. Nothing was "
            f"written to the tenant; a collector has no write path.",
            file=sys.stderr,
        )
        _report_manifest(outcome)
        return 1

    if state is collecting.State.CANCELLED:
        # What was already written stays, and says what it covers. Deleting it
        # would throw away a reading somebody may still want, and keeping it
        # silently would let it pass for a complete one.
        print(
            f"\ncancelled after {outcome.seconds:.1f}s. "
            f"{len(outcome.written)} evidence documents were already written "
            f"and are kept; they describe only what had been read by then.",
            file=sys.stderr,
        )
        _report_gaps(outcome)
        _report_manifest(outcome)
        return 1

    if state is collecting.State.PARTIAL:
        # NOT A FAILURE, and the exit code says so. A collection that reached
        # part of an estate produced evidence worth exactly that part, and
        # rules over it answer `unknown` where the gap could change them.
        print(
            f"\n{len(outcome.written)} evidence documents in "
            f"{outcome.seconds:.1f}s, and the collection is PARTIAL."
        )
        _report_gaps(outcome)
        if outcome.returncode != 0:
            print(
                "  the collector stopped before finishing; what it had already "
                "written is above",
            )
        print(
            "\nEvaluating this is valid. Where the gap could change an answer, "
            "a rule returns `unknown` rather than a pass."
        )
    else:
        print(f"\n{len(outcome.written)} evidence documents in {outcome.seconds:.1f}s.")
    _report_manifest(outcome)
    # Named rather than assumed: the pairing between a collection and the
    # rules that read it is the difference between a report and a wall of
    # `unknown` for facts nobody requested.
    print(
        f"Evaluate with:  m365-governance evaluate --profile "
        f"profiles/{chosen.profile}.yaml --evidence {args.output}"
    )
    return 0


def _cmd_connect(args) -> int:
    """Reach a tenant, and say what was established.

    The other half of `doctor`. That one answers whether this installation is
    sound; nothing answered whether the application registration in front of
    you can reach the tenant in front of you, and as whom — which was found out
    several minutes into a collection, from a failure that looked like a tenant
    problem rather than a consent problem.
    """
    try:
        _project(args)
        _authentication(args)
    except AmbiguousIdentity as refusal:
        print(f"refusing to run: {refusal}", file=sys.stderr)
        return 2

    for problem in collecting.preflight():
        print(problem, file=sys.stderr)
        return 2

    if not args.site_url and not args.tenant_url:
        print(
            "connect needs --tenant-url or --site-url: an address to reach.",
            file=sys.stderr,
        )
        return 2

    # Printed as it arrives, and this one is not a convenience. A device-code
    # sign-in prints a code somebody has to read off the screen, so buffering
    # would ask a person to wait for something they had already been shown.
    def report(line: str) -> None:
        if args.format != "text":
            return
        shown = connecting.readable(line)
        if shown is not None:
            print(shown, flush=True)

    established = connecting.connect(
        client_id=args.client_id,
        site_url=args.site_url,
        tenant_url=args.tenant_url,
        device_login=args.device_login,
        dry_run=args.dry_run,
        certificate_path=str(args.certificate_path) if args.certificate_path else None,
        tenant_id=args.tenant_id,
        certificate_password_env=args.certificate_password_env,
        on_progress=None if args.dry_run else report,
    )

    if args.dry_run:
        print(established.output[0])
        return 0

    if args.format == "json":
        # The contract, not a rendering of the object. A consumer validates this
        # against `connection/1.0.0` and deserialises it, exactly as it does for
        # every other document this engine writes.
        print(json.dumps(connecting.document(established), indent=2))
    else:
        print()
        sys.stdout.write(connecting.describe(established))

    return 0 if established.reach is connecting.Reach.ESTABLISHED else 1


def _cmd_run(args) -> int:
    """A configured target to a report, without learning what a slice is.

    IT COMPOSES; IT DECIDES NOTHING NEW. Every step here is a command that
    already exists, called in the order somebody would have called them, and
    the reason it exists is that choosing among ten slices is a decision this
    engine can make from the target it was given. Asking a person to make it
    before they have seen one finding is asking them to learn the architecture
    in order to use the tool.

    A COLLECTION THAT FAILED DOES NOT END THE RUN. Six of fifty-three sites
    refusing a collector is a fact about coverage, not a reason to produce
    nothing; the manifest carries what each collection turned out to be, and
    the report is built over what was actually gathered.
    """
    try:
        _project(args)
        _authentication(args)
    except AmbiguousIdentity as refusal:
        print(f"refusing to run: {refusal}", file=sys.stderr)
        return 2

    steps = running.plan(
        site_url=args.site_url,
        tenant_url=args.tenant_url,
        has_graph_token=bool(os.environ.get(conditional_access.TOKEN_VARIABLE)),
    )
    doing = running.attempted(steps)
    sys.stderr.write(running.describe(steps))

    if not doing:
        print(
            "\nnothing to collect: the target names neither a site nor an "
            "admin address. Add one to the project file, or pass --site-url "
            "or --tenant-url.",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        return 0

    for problem in collecting.preflight():
        print(problem, file=sys.stderr)
        return 2

    for step in doing:
        print(f"\ncollecting {step.name}", file=sys.stderr, flush=True)
        outcome = collecting.run_slice(
            step.name,
            client_id=args.client_id,
            output=args.output,
            site_url=args.site_url,
            tenant_url=args.tenant_url,
            device_login=args.device_login,
            tenant_id=args.tenant_id,
            certificate_path=args.certificate_path,
            certificate_password_env=args.certificate_password_env,
            on_progress=lambda line: print(f"  {line}", file=sys.stderr, flush=True),
        )
        # Reported, never fatal. What a collection turned out to be is carried
        # in its own manifest, and a run that stopped at the first refusal
        # would throw away every slice that did work.
        print(f"  {step.name}: {outcome.state}", file=sys.stderr)

    # From here it is `evaluate`, on the evidence just gathered. The arguments
    # it reads are set rather than a second implementation of it: two ways to
    # evaluate would eventually disagree, and the one nobody tested would win.
    args.evidence = args.output
    try:
        runs, _documents = _evaluate_all(args)
    except _Refused:
        return 2
    if not runs:
        print(f"{args.output}: nothing was collected", file=sys.stderr)
        return 2

    report = _render_many(RunSet(runs), args.format)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"\n{args.out}", file=sys.stderr)
    else:
        sys.stdout.write(report)

    return _exit_for(runs, args.fail_on)


def _exit_for(runs: list[Run], fail_on: str) -> int:
    """One reading of `--fail-on`, shared by `evaluate` and `run`."""
    counts = {outcome.value: 0 for outcome in Outcome}
    for run in runs:
        for key, value in run.counts().items():
            counts[key] += value
    if fail_on == "fail" and counts[Outcome.FAIL.value]:
        return 1
    if fail_on == "unresolved":
        unresolved = (
            counts[Outcome.FAIL.value]
            + counts[Outcome.UNKNOWN.value]
            + counts[Outcome.INVALID_EVIDENCE.value]
            + counts[Outcome.ERROR.value]
        )
        if unresolved:
            return 1
    return 0


#: How to obtain the one input nothing works without. It is a single command,
#: it is documented by PnP, and until now this product named neither: the only
#: instruction anywhere was "register an Entra ID app, or use one your tenant
#: already has", which is the hardest step described as an aside.
REGISTRATION = """Register-PnPEntraIDAppForInteractiveLogin \\
    -ApplicationName "M365 Governance" \\
    -Tenant <your-tenant>.onmicrosoft.com"""


def _cmd_setup(args) -> int:
    """Prepare a machine, and write down the target once. Reaches no tenant.

    THE HALF OF `doctor` THAT TOLD NOBODY WHAT TO DO. `doctor` says what is
    missing, and for one dependency it says how to fix it; for the step that
    actually stops people -- obtaining an application registration -- nothing
    in this product said anything at all, and the answer is one documented
    command.

    IT REGISTERS NOTHING ITSELF. This engine reads and acquires nothing:
    creating a registration changes a directory, and a read-only product that
    quietly wrote to a tenant during setup would have a write path after all.
    It prints the command; a person runs it, in their own tenant, knowingly.
    """
    # `doctor`'s own report, whole. A second rendering of the same checks would
    # be a second thing to keep true, and the two would disagree the first time
    # a check was added to one of them.
    text, healthy = doctor_module.report()
    sys.stdout.write(text)

    if not healthy:
        print(
            "\nSetup stops here: the environment is not sound yet, and a "
            "project file naming a tenant would be the least of the problems.",
            file=sys.stderr,
        )
        return 2

    if not args.client_id:
        print(
            "\nNext: an application registration.\n\n"
            "  Every connection needs one, and there is no default: "
            "PnP.PowerShell has\n"
            "  shipped no application of its own since 2.12.0. One "
            "registration serves\n"
            "  every run. In PowerShell, in your own tenant:\n\n"
            f"    {REGISTRATION}\n\n"
            "  It prints the id it registered. Then run this again with it:\n\n"
            "    m365-governance setup --client-id <id> "
            "--tenant-url https://<tenant>-admin.sharepoint.com\n"
        )
        # Not a failure. The environment is sound and the person has been told
        # the one thing they did not have; exiting non-zero would report a
        # broken installation to a pipeline that has none.
        return 0

    try:
        _application_id(args.client_id)
    except AmbiguousIdentity as refusal:
        print(f"refusing to write: {refusal}", file=sys.stderr)
        return 2

    if not args.site_url and not args.tenant_url:
        print(
            "setup needs --tenant-url or --site-url: a project file with no "
            "target names nothing to assess.",
            file=sys.stderr,
        )
        return 2

    if args.out.exists() and not args.force:
        print(
            f"{args.out} already exists. It carries a target somebody chose, "
            f"and overwriting it silently would repoint every later run. "
            f"Pass --force to replace it.",
            file=sys.stderr,
        )
        return 2

    args.out.write_text(_project_text(args), encoding="utf-8")
    print(f"\nWrote {args.out}\n")
    print("Next:\n")
    print("  m365-governance connect        # prove the identity can work here")
    print("  m365-governance run            # collect, assess and report\n")
    return 0


def _project_text(args) -> str:
    """The project file, written for a person to read and edit afterwards.

    NO CREDENTIAL IS EVER WRITTEN HERE, and the header says so in the file
    rather than only in the documentation: this file is committed, copied into
    tickets and pasted into chats, and the person who would put a password in
    one is not reading the manual at that moment.
    """
    lines = [
        "# Written by `m365-governance setup`. Edit it freely.",
        "#",
        "# NO SECRET BELONGS IN THIS FILE. It is committed, copied into tickets",
        "# and pasted into chats. A certificate password is named here by the",
        "# environment variable that holds it, never by its value.",
        "",
        "[target]",
    ]
    if args.tenant_url:
        lines.append(f'tenant_url = "{args.tenant_url}"')
    if args.site_url:
        lines.append(f'site_url = "{args.site_url}"')
    lines += ["", "[identity]", f'client_id = "{args.client_id}"']
    if args.tenant_id:
        lines.append(f'tenant_id = "{args.tenant_id}"')
    if args.certificate_path:
        lines.append(f'certificate_path = "{args.certificate_path}"')
    if args.certificate_password_env:
        lines.append(f'certificate_password_env = "{args.certificate_password_env}"')
    return "\n".join(lines) + "\n"


def _cmd_explain(args) -> int:
    sys.stdout.write(explaining.explain(args.outcome))
    return 0


def _cmd_doctor(args) -> int:
    text, healthy = doctor_module.report(args.root.resolve() if args.root else None)
    sys.stdout.write(text)
    return 0 if healthy else 1


def _cmd_stats(args) -> int:
    sys.stdout.write(inspect_module.stats(args.evidence))
    return 0


# ---------------------------------------------------------------------------
# producing a result
# ---------------------------------------------------------------------------


def _cmd_validate(args) -> int:
    source = _rule_source(args)
    problems = validate_rules(source.path)
    if not problems:
        count = len(list(source.path.rglob("*.yaml")))
        print(f"{count} rules validated. No problems found.")
        return 0
    for problem in sorted(problems, key=lambda p: (p.layer, p.location, p.code)):
        print(problem, file=sys.stderr)
    print(f"\n{len(problems)} problems.", file=sys.stderr)
    return 1


def _render(run: Run, fmt: str) -> str:
    if fmt == "json":
        return to_json(run)
    if fmt == "html":
        return to_html(run)
    return to_markdown(run)


def _render_many(run_set: RunSet, fmt: str) -> str:
    """The run-set envelope, in whichever format was asked for.

    Every format renders the same run set, so `report` and `evaluate` cannot
    disagree about a tenant depending on the flag that was passed.
    """
    if fmt == "json":
        return many_to_json(run_set)
    if fmt == "html":
        return many_to_html(run_set)
    return many_to_markdown(run_set)


def _rule_source(args) -> Source:
    return resolve("rules", getattr(args, "rules", None))


class ProfileNotFound(SystemExit):
    """A profile nobody can resolve. Never a silent full evaluation."""


def _profile_source(args) -> Source:
    """A packaged name first, then a path, and an error if neither.

    THIS FAILED OPEN AND IT WAS PROVEN. `--profile sharing` was read as a
    relative path, the path did not exist, the selection was skipped, and every
    rule ran: thirteen instead of two, eleven of them reporting `unknown` about
    facts nobody asked for. `unknown` is this product's most trusted state, and
    producing it from a bug is worse than an error.

    The same mistake was printed by the tool itself after a collection, and
    reached a consumer's fixture generator, so two fixtures documented as
    different scenarios were byte-identical in rule set.

    A selection contract must be total. An unresolvable name stops the run and
    names what exists.
    """
    supplied = getattr(args, "profile", None)
    packaged = resolve("profiles", None).path

    if supplied is None:
        return Source(path=packaged / "default.yaml", origin="package")

    by_name = packaged / f"{supplied}.yaml"
    if by_name.exists():
        return Source(path=by_name, origin="package")

    as_path = Path(supplied)
    if as_path.exists():
        return Source(path=as_path, origin="external")

    known = ", ".join(sorted(p.stem for p in packaged.glob("*.yaml")))
    raise ProfileNotFound(
        f"\nno profile {str(supplied)!r}.\n"
        f"  packaged profiles: {known}\n"
        f"  or give a path to a profile file.\n"
        f"Refusing to run: evaluating every rule instead of the ones you asked "
        f"for would report facts nobody requested as `unknown`.\n"
    )


def _load_rules_for(args) -> list[dict]:
    rules = [loaded.data for loaded in load_rules(_rule_source(args).path)]
    profile = _profile_source(args).path
    if profile.exists():
        # A profile with no `rules` key selects everything. Reading that as an
        # empty selection would silently evaluate nothing.
        selected = load_profile(profile).get("rules")
        if selected:
            rules = [r for r in rules if r["id"] in selected]
    return rules


def _evidence_documents(path: Path) -> list[Path]:
    """Every evidence document under `--evidence`. A manifest is not one.

    The exclusion is by name and it is deliberate: a collection manifest is a
    `.json` file sitting among the documents it describes, and validating it as
    evidence would refuse a whole evaluation over a document that is not
    evidence and never claimed to be.
    """
    if path.is_dir():
        return sorted(
            found
            for found in path.rglob("*.json")
            if not found.name.startswith("collection-manifest")
        )
    if not path.exists():
        # Named here rather than left to the loader, because at this point the
        # caller may have meant either a document or a directory of them, and
        # a message that guessed one of the two would send half of them looking
        # for the wrong mistake.
        raise DocumentError(f"{path}: no such file or directory")
    return [path]


def _report_collections(evidence: Path) -> None:
    """What the collections that produced this evidence say about themselves.

    CONSERVATIVE ON PURPOSE. Where a manifest exists it is used, because the
    collection said what it did. Where none exists nothing is claimed: evidence
    collected before this contract, or exported from elsewhere, carries no
    account of its own completeness, and inventing one here would be the engine
    reporting a gap it never measured as an absence of gaps.
    """
    found = collecting.manifests(evidence)
    if not found:
        return

    short = [m for m in found if m.get("state") != "completed"]
    if not short:
        print(
            f"{len(found)} collections produced this evidence, all complete.",
            file=sys.stderr,
        )
        return

    print(
        f"{len(found)} collections produced this evidence, {len(short)} of them "
        f"incomplete. What follows is bounded by what was read:",
        file=sys.stderr,
    )
    for manifest in short:
        name = manifest.get("slice", {}).get("name", "?")
        print(f"  {name}: {manifest.get('state')}", file=sys.stderr)
        for reason in manifest.get("because", []):
            print(f"    {reason}", file=sys.stderr)


def _set_aside_classes(profile_path: Path) -> set[str]:
    """Which classes a profile moves down the page.

    Never which it removes. A profile that could drop a resource could hide a
    library holding 60,000 unique scopes because SharePoint calls it plumbing,
    and the whole point of classifying was to reduce noise without losing
    facts.
    """
    if not profile_path.exists():
        return set()
    return set(load_profile(profile_path).get("set_aside_classes") or [])


class _Refused(Exception):
    """Something was already printed to stderr and the command is over."""


def _evaluate_all(args) -> tuple[list[Run], list[dict]]:
    """Every evidence document under `--evidence`, evaluated.

    Shared by `evaluate` and `assess` so the two cannot disagree about what a
    run is. The documents come back alongside the runs because an assessment
    carries the evidence whole, and reading it a second time from disk would
    let the two halves describe different bytes.
    """
    problems = validate_rules(_rule_source(args).path)
    if problems:
        print(
            "refusing to evaluate: the rules do not validate. "
            "Run `m365-governance validate`.",
            file=sys.stderr,
        )
        raise _Refused

    rules = _load_rules_for(args)
    aside = _set_aside_classes(_profile_source(args).path)

    # Before the results, not after. What was read bounds everything that
    # follows, and a bound printed underneath a conclusion arrives too late to
    # change how the conclusion is read.
    _report_collections(args.evidence)

    documents = []
    for path in _evidence_documents(args.evidence):
        data = load_evidence(path).data
        problems = validate_evidence_document(data, str(path))
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            print(
                f"\nrefusing to evaluate {path}: the evidence does not match "
                f"the schema. This is a defect in the collector, not a finding "
                f"about the resource.",
                file=sys.stderr,
            )
            raise _Refused
        documents.append(data)

    # ONE RESOURCE, HOWEVER MANY COLLECTORS DESCRIBED IT.
    # `collect` writes a document per slice and a run set holds a run per
    # resource, and between those two correct decisions there was nothing: two
    # slices of one site produced two documents and `assess` refused them. The
    # only way through was to merge the files by hand, which is evidence edited
    # between the command that wrote it and the command that reads it.
    #
    # The composition is for EVALUATION. `documents` stays as it was, so the
    # assessment still carries what each collector actually wrote.
    try:
        composed = composing.compose(documents)
    except composing.Conflict as clash:
        print(f"refusing to evaluate: {clash}", file=sys.stderr)
        raise _Refused from clash

    # WITHOUT A PROFILE, THE SCOPE IS WHAT WAS COLLECTED.
    # `default.yaml` selects every rule, and against a slice's evidence that
    # means evaluating questions the collection never asked: the first real
    # tenant run produced 742 unknowns out of 795, each one saying only that
    # this document does not carry that evidence. A caller who names a profile
    # has chosen; a caller who names none gets the questions their evidence can
    # speak to, and `--profile default.yaml` still asks everything.
    # The DEFAULT profile, not the resolution: `_profile_source` returns
    # `default.yaml` when nothing was supplied, and default.yaml is every rule.
    # Its own docstring names this failure -- evaluating every rule reports
    # facts nobody requested as `unknown` -- and closes the case where a
    # profile name does not resolve. The case where none was given stayed open.
    scoped = getattr(args, "profile", None) is None
    runs = []
    for data in composed:
        run = evaluate(rules, data, only_collected=scoped)
        run.set_aside = run.resource_class in aside
        run.rule_source = _rule_source(args).describe()
        runs.append(run)
    return runs, documents


def _cmd_evaluate(args) -> int:
    try:
        runs, _ = _evaluate_all(args)
    except _Refused:
        return 2

    # The shape follows what was asked for, not how many files happened to be
    # there. A directory with one document in it today and three tomorrow must
    # not change the shape of what a pipeline parses. A directory is always a
    # run set; a single file is always one run. Building the set here, once, is
    # also where two documents about the same resource are refused, before any
    # format sees them.
    if not args.evidence.is_dir():
        sys.stdout.write(_render(runs[0], args.format))
    else:
        sys.stdout.write(_render_many(RunSet(runs), args.format))

    return _exit_for(runs, args.fail_on)


def _cmd_assess(args) -> int:
    """Evaluate, and package the result so somebody else can check it.

    The difference from `evaluate` is not the format. An assessment carries the
    evidence it was decided from, the versions that decided it, and digests
    over all of it, so a person who receives one can establish that nothing
    moved without having this engine or trusting whoever sent it.
    """
    try:
        runs, documents = _evaluate_all(args)
    except _Refused:
        return 2
    if not runs:
        print(f"{args.evidence}: no evidence documents", file=sys.stderr)
        return 2

    # From the clock only here, at the boundary. `build` takes it as a value so
    # that the same inputs produce the same bytes: an assessment whose digest
    # moved because time passed would be unverifiable by construction, and
    # `--created-at` is what makes rebuilding one possible.
    created_at = args.created_at or datetime.now(UTC).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    try:
        document = assessment.build(
            RunSet(runs),
            documents,
            engine_version=__version__,
            created_at=created_at,
            label=args.label,
        )
    except assessment.Mismatch as exc:
        # Not a traceback and not a finding: the manifest would have said
        # something this evidence does not support, and the caller needs the
        # sentence rather than the stack.
        print(f"refusing to assemble an assessment: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        manifest = document["canonical"]["manifest"]
        print(f"{manifest['assessment_id']}  {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def _cmd_migration_read(args) -> int:
    """One estate, one moment, one authenticated session.

    The token is spent, never acquired. Every dimension this read carries comes
    from the same session: an interactive sign-in per dimension is the mistake
    this product already measured once, and repeating it here would multiply it
    by the number of things worth comparing.
    """
    token = os.environ.get(migration_graph_token := "M365_GOVERNANCE_GRAPH_TOKEN")
    if not token:
        print(
            f"{migration_graph_token} is not set. This command spends a token "
            "somebody already holds; it never acquires one.",
            file=sys.stderr,
        )
        return 2

    try:
        reader = graph.GraphReader(token)
        document = migration_graph.read(
            reader,
            drive=args.drive,
            folder=args.folder,
            read_id=args.read_id,
            taken_at=args.taken_at,
            estate=args.estate,
            with_versions=args.with_versions,
            with_permissions=args.with_permissions,
        )
    except (graph.Refused, migration_graph.Unreadable) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(canonical.encode(document) + b"\n")

    carried = sorted({key for item in document["items"].values() for key in item})
    print(f"{document['estate']}")
    print(f"  read          {document['read_id']} ({document['taken_at']})")
    print(f"  items         {len(document['items'])}")
    print(f"  carried       {', '.join(carried) or 'identity only'}")
    if document.get("content_digest_algorithm"):
        print(f"  digest        {document['content_digest_algorithm']}")
    for gap in document["coverage"]:
        print(f"  not read      {gap['scope']} ({gap['state']})")
    print(f"  digest        {canonical.digest(document)}")

    # Coverage is not failure. A read that states what it could not reach is
    # doing its job; only an estate nobody could enumerate at all is an error,
    # and that raised before reaching here.
    return 0


def _cmd_migration_verify(args) -> int:
    """Two reads in, a verification record out, and refusals said out loud.

    The record is refused rather than produced when the inputs cannot support
    it — a baseline that is not earlier, or one read handed in twice. Printing
    a warning and continuing would put the operator's mistake inside a document
    that then travels as evidence.
    """
    reads = []
    # `which` is not read: the pair exists so the two sides are walked in a
    # fixed order, and the name documents which is which at the call site.
    for _which, path in (
        ("baseline", args.baseline),
        ("verification", args.verification),
    ):
        document = load_evidence(path).data
        if document.get("$schema") != migration.read_contract():
            print(
                f"{path}: not a migration read. It must declare "
                f"{migration.read_contract()}",
                file=sys.stderr,
            )
            return 2
        reads.append(document)

    move = {"kind": args.kind, "produced_by": f"m365-governance {__version__}"}
    if args.performed_by:
        move["performed_by"] = args.performed_by

    try:
        document = migration.record(baseline=reads[0], verification=reads[1], move=move)
    except migration.Unverifiable as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(canonical.encode(document) + b"\n")
    if args.report:
        fmt = args.report_format or (
            "html" if args.report.suffix.lower() in (".html", ".htm") else "markdown"
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(migration.report(document, fmt), encoding="utf-8")

    compared = [d["name"] for d in document["dimensions"] if d["state"] == "compared"]
    skipped = [d for d in document["dimensions"] if d["state"] != "compared"]
    counts: dict[str, int] = {}
    for finding in document["findings"]:
        counts[finding["outcome"]] = counts.get(finding["outcome"], 0) + 1

    print(f"{document['baseline']['estate']}")
    print(
        f"  baseline      {document['baseline']['read_id']} "
        f"({document['baseline']['taken_at']})"
    )
    print(
        f"  verification  {document['verification']['read_id']} "
        f"({document['verification']['taken_at']})"
    )
    print(f"  compared      {', '.join(compared)}")
    for entry in skipped:
        print(f"  not compared  {entry['name']}: {entry['reason']}")
    for gap in document["baseline"]["coverage"] + document["verification"]["coverage"]:
        print(f"  not read      {gap['scope']} ({gap['state']})")
    if not document["findings"]:
        print("  nothing to report, within the coverage above")
    for outcome in ("fail", "unknown", "invalid-evidence"):
        if counts.get(outcome):
            print(f"  {outcome:<13} {counts[outcome]}")
    print(f"  digest        {migration.digest(document)}")

    # `unknown` is not a failure and does not become one here. An operator who
    # could not read half the estate has a coverage problem, not a migration
    # problem, and conflating them is what this whole contract refuses.
    return 1 if counts.get("fail") or counts.get("invalid-evidence") else 0


def _cmd_verify(args) -> int:
    """What is wrong with an assessment that arrived, or nothing.

    Deliberately its own command. Verifying is what somebody does to a document
    they received, and a check that needed the producer would only ever be
    telling them what the producer already believes.
    """
    document = load_evidence(args.assessment).data
    if "canonical" not in document:
        print(
            f"{args.assessment}: not an assessment. `verify` checks the "
            f"document `assess` writes; to re-render a report use `report`.",
            file=sys.stderr,
        )
        return 2

    problems = assessment.verify(document)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"\n{args.assessment} does not verify.", file=sys.stderr)
        return 1

    manifest = document["canonical"]["manifest"]
    print(f"{manifest['assessment_id']}")
    tenant = manifest["tenant"]
    print(f"  tenant     {tenant['host']}")
    if tenant["id"]:
        print(f"  directory  {tenant['id']}")
    identity = manifest["identity"]
    print(f"  identity   {identity['summary']}: {', '.join(identity['kinds']) or '—'}")
    acquired = manifest["acquisition"]
    print(f"  acquired   {', '.join(acquired['kinds'])}")
    print(f"  created    {manifest['created_at']}")
    if manifest.get("label"):
        print(f"  label      {manifest['label']}")
    print(f"  resources  {document['canonical']['run_set']['resources']}")
    print(f"  evidence   {len(document['canonical']['evidence'])} documents")
    return 0


def _read_run_or_set(path: Path, rules_dir: Path) -> Run | RunSet:
    """A stored run, a stored run set, or an evidence document evaluated now.

    Accepting all three is not convenience. Somebody comparing two runs has a
    mix often enough: last quarter was archived as a report, this morning is a
    fresh collection, and refusing to compare them would send them to
    regenerate something they already have. A run set is the same story at
    tenant scale, where the archive is a whole estate rather than one site.
    """
    data = load_evidence(path).data
    # An assessment carries its run set inside the canonical half. Comparing
    # two of them is comparing what they concluded, and unwrapping here means
    # `diff` never learns a second shape.
    if "canonical" in data:
        return RunSet.from_dict(data["canonical"]["run_set"])
    if "runs" in data:
        return RunSet.from_dict(data)
    if "results" in data:
        return Run.from_dict(data)
    if "facts" in data:
        rules = [loaded.data for loaded in load_rules(rules_dir)]
        return evaluate(rules, data)
    raise DocumentError(
        f"{path}: neither a report (no `results` or `runs`) nor evidence (no `facts`)"
    )


def _cmd_report(args) -> int:
    data = load_evidence(args.report).data
    # An assessment is rendered from its canonical half, never from anything
    # stored under `derived`: a report that could not be regenerated from what
    # was archived would be a second original rather than a projection.
    if "canonical" in data:
        data = data["canonical"]["run_set"]
    # A run set carries `runs`; a single run carries `results`. `report` renders
    # whichever `evaluate` wrote, in whichever format is asked for now.
    if "runs" in data:
        sys.stdout.write(_render_many(RunSet.from_dict(data), args.format))
        return 0
    if "results" in data:
        sys.stdout.write(_render(Run.from_dict(data), args.format))
        return 0
    print(
        f"{args.report}: not a report. `report` re-renders a stored run or run "
        f"set; to evaluate evidence use `evaluate`.",
        file=sys.stderr,
    )
    return 2


def _cmd_diff(args) -> int:
    """What changed between two assessments.

    A COMPARISON RELATES TWO STATES AND BELONGS TO NEITHER, which is why it is
    its own document rather than a section of an assessment. It names each side
    by identity and digest and embeds neither: a comparison carrying both would
    duplicate the canonical truth it describes, and the copy is what somebody
    edits.

    It takes assessments and not runs. A run is an evaluation; an assessment is
    the thing somebody archived, and only an assessment can be named by an
    identity that verifies. Comparing what a run-level diff compares is still
    how this is computed underneath — it just is not a document anybody keeps.
    """
    documents = {}
    for side, path in (("before", args.before), ("after", args.after)):
        data = load_evidence(path).data
        if "canonical" not in data:
            print(
                f"{path}: not an assessment. `diff` compares two assessments, "
                f"which `assess` writes; a stored run is not one.",
                file=sys.stderr,
            )
            return 2
        documents[side] = data

    try:
        document = comparison.build(
            documents["before"], documents["after"], engine_version=__version__
        )
    except comparison.Incomparable as exc:
        print(f"refusing to compare: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        sys.stdout.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(reporting.comparison_to_markdown(document))

    if args.fail_on_regression:
        # A regression is leaving `pass`, and only the engine's own outcomes
        # decide that. Nothing here re-reads evidence to form a second opinion.
        left = [
            change
            for change in document["diff"]["changes"]
            if change["before"] == "pass" and change["after"] != "pass"
        ]
        if left:
            return 1
    return 0


def _cmd_contracts(args) -> int:
    """Write the vendored bundle from THIS INSTALLATION.

    WHY A COMMAND AND NOT A DOCUMENT IN THE REPOSITORY. A consumer that had to
    clone this repository to obtain the contract could only be as current as
    whoever last remembered to copy it, and nothing could answer "is this
    bundle current?" by any automated means. The bundle now ships in the wheel,
    so `pip install` and this command are enough — and the version it declares
    is the engine's own, which moves when the engine is released.
    """
    root = packaged("generated")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for sub in ("schemas", "csharp"):
        target = out / sub
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

    data = packaged("schemas").parent
    for entry in manifest["schemas"].values():
        source = data / entry["path"]
        target = out / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    for model in sorted((root / "csharp").glob("*.g.cs")):
        shutil.copy2(model, out / "csharp" / model.name)
    shutil.copy2(root / "manifest.json", out / "manifest.json")

    print(
        f"contract {manifest['contract_version']} written to {out}: "
        f"{len(manifest['schemas'])} schemas, {len(manifest['generated'])} models"
    )
    return 0


_COMMANDS = {
    "list-rules": _cmd_list_rules,
    "show-rule": _cmd_show_rule,
    "capabilities": _cmd_capabilities,
    "collect": _cmd_collect,
    "connect": _cmd_connect,
    "run": _cmd_run,
    "setup": _cmd_setup,
    "explain": _cmd_explain,
    "doctor": _cmd_doctor,
    "stats": _cmd_stats,
    "validate": _cmd_validate,
    "evaluate": _cmd_evaluate,
    "assess": _cmd_assess,
    "verify": _cmd_verify,
    "migration-read": _cmd_migration_read,
    "migration-verify": _cmd_migration_verify,
    "report": _cmd_report,
    "diff": _cmd_diff,
    "contracts": _cmd_contracts,
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except DuplicateResource as exc:
        # Two documents about one resource. One sentence, not a traceback: the
        # engine is refusing to average two answers, and the caller needs to
        # know which resource, not where in the code it was caught.
        print(f"{exc}", file=sys.stderr)
        return 2
    except DocumentError as exc:
        print(f"document error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"not valid JSON: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
