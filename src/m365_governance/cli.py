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
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__, assessment, collecting, diffing, explaining
from . import doctor as doctor_module
from . import inspect as inspect_module
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
from .resources import Source, resolve
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
        required=True,
        help="an Entra ID app registration. Mandatory since PnP 2.99",
    )
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--site-url")
    collect.add_argument("--tenant-url", help="https://<tenant>-admin.sharepoint.com")
    collect.add_argument(
        "--device-login",
        action="store_true",
        help="authenticate with a device code, for hosts with no browser",
    )
    collect.add_argument(
        "--count-unique-scopes",
        action="store_true",
        help="permissions only: walk every item of every list",
    )
    collect.add_argument(
        "--dry-run", action="store_true", help="print the command and reach no tenant"
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
        "diff", help="what changed between two runs, and whether the rule moved too"
    )
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--rules", type=Path, default=None, help=RULES_HELP)
    diff.add_argument("--format", choices=("markdown", "json"), default="markdown")
    diff.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit non-zero when any rule left `pass`",
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


def _cmd_collect(args) -> int:
    chosen = collecting.SLICES[args.slice]

    for problem in collecting.preflight():
        print(problem, file=sys.stderr)
        return 2

    if chosen.needs_site and not args.site_url:
        print(f"collect {args.slice} needs --site-url", file=sys.stderr)
        return 2
    if chosen.needs_tenant and not args.tenant_url:
        print(
            f"collect {args.slice} needs --tenant-url, the admin centre. "
            f"Sharing settings are a tenant property about a site.",
            file=sys.stderr,
        )
        return 2

    outcome = collecting.run_slice(
        args.slice,
        client_id=args.client_id,
        output=args.output,
        site_url=args.site_url,
        tenant_url=args.tenant_url,
        device_login=args.device_login,
        count_unique_scopes=args.count_unique_scopes,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(outcome.stdout)
        return 0

    if outcome.stdout.strip():
        print(outcome.stdout.rstrip())
    if not outcome.ok:
        print(outcome.stderr.rstrip(), file=sys.stderr)
        print(
            f"\ncollection failed after {outcome.seconds:.1f}s. Nothing was "
            f"written to the tenant; a collector has no write path.",
            file=sys.stderr,
        )
        return 1

    print(f"\n{len(outcome.written)} evidence documents in {outcome.seconds:.1f}s.")
    # Named rather than assumed: the pairing between a collection and the
    # rules that read it is the difference between a report and a wall of
    # `unknown` for facts nobody requested.
    print(
        f"Evaluate with:  m365-governance evaluate --profile "
        f"profiles/{chosen.profile}.yaml --evidence {args.output}"
    )
    return 0


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
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    return [path]


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

    runs, documents = [], []
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
        run = evaluate(rules, data)
        run.set_aside = run.resource_class in aside
        run.rule_source = _rule_source(args).describe()
        runs.append(run)
        documents.append(data)
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

    counts = {o.value: 0 for o in Outcome}
    for run in runs:
        for key, value in run.counts().items():
            counts[key] += value
    if args.fail_on == "fail" and counts[Outcome.FAIL.value]:
        return 1
    if args.fail_on == "unresolved":
        unresolved = (
            counts[Outcome.FAIL.value]
            + counts[Outcome.UNKNOWN.value]
            + counts[Outcome.INVALID_EVIDENCE.value]
            + counts[Outcome.ERROR.value]
        )
        if unresolved:
            return 1
    return 0


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
    print(f"  tenant     {manifest['tenant']}")
    print(f"  identity   {manifest['identity_kind']}")
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
    rules_path = _rule_source(args).path
    before = _read_run_or_set(args.before, rules_path)
    after = _read_run_or_set(args.after, rules_path)

    # A run and a run set are not comparable: one is a resource, the other an
    # estate, and pretending would either hide every other resource or invent
    # one. Refuse rather than guess.
    if isinstance(before, RunSet) != isinstance(after, RunSet):
        print(
            "cannot diff a single resource against a run set. Compare a run "
            "with a run, or a run set with a run set.",
            file=sys.stderr,
        )
        return 2

    # Markdown is what a person reads; JSON is what everything else reads. Both
    # are projections of one comparison, so they cannot disagree about what
    # changed.
    as_json = args.format == "json"
    if isinstance(before, RunSet):
        sys.stdout.write(
            diffing.many_to_json(before, after)
            if as_json
            else diffing.many_to_markdown(before, after)
        )
        changes = [
            rc for change in diffing.compare_sets(before, after) for rc in change.rules
        ]
    else:
        sys.stdout.write(
            diffing.to_json(before, after)
            if as_json
            else diffing.to_markdown(before, after)
        )
        changes = diffing.compare(before, after)

    if args.fail_on_regression and diffing.regressions(changes):
        return 1
    return 0


_COMMANDS = {
    "list-rules": _cmd_list_rules,
    "show-rule": _cmd_show_rule,
    "collect": _cmd_collect,
    "explain": _cmd_explain,
    "doctor": _cmd_doctor,
    "stats": _cmd_stats,
    "validate": _cmd_validate,
    "evaluate": _cmd_evaluate,
    "assess": _cmd_assess,
    "verify": _cmd_verify,
    "report": _cmd_report,
    "diff": _cmd_diff,
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
