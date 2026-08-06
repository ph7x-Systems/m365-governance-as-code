"""Command line.

Nothing here writes to a tenant. There is no write path in this system:
remediation is text in a rule, addressed to a person.

The commands split into three kinds, and the split is worth keeping:

  read the repository   list-rules, show-rule, doctor
  read the evidence     stats
  produce a result      validate, evaluate, report, diff

Only the last kind reaches a conclusion, and only `evaluate` reaches a new one.
`report` and `diff` re-read conclusions somebody already stored, which is why
they never need rules: a stored report carries what it was decided from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, collecting, diffing, explaining
from . import doctor as doctor_module
from . import inspect as inspect_module
from .engine import evaluate
from .loader import DocumentError, load_evidence, load_profile, load_rules
from .reporting import many_to_json, many_to_markdown, to_html, to_json, to_markdown
from .results import Outcome, Run
from .validator import validate_evidence_document, validate_rules

DEFAULT_RULES = Path("rules")
DEFAULT_PROFILE = Path("profiles/default.yaml")


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
    listing.add_argument("--rules", type=Path, default=DEFAULT_RULES)

    showing = sub.add_parser(
        "show-rule", help="one rule in full, including what it does not establish"
    )
    showing.add_argument("rule_id", metavar="ID")
    showing.add_argument("--rules", type=Path, default=DEFAULT_RULES)

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
    doc.add_argument("--root", type=Path, default=Path("."))

    stats = sub.add_parser(
        "stats", help="what a collector managed to see, before evaluating it"
    )
    stats.add_argument("evidence", type=Path)

    validate = sub.add_parser(
        "validate", help="check every rule against the schemas and the invariants"
    )
    validate.add_argument("--rules", type=Path, default=DEFAULT_RULES)

    evaluate_cmd = sub.add_parser(
        "evaluate", help="run rules against an evidence document"
    )
    evaluate_cmd.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    evaluate_cmd.add_argument("--evidence", type=Path, required=True)
    evaluate_cmd.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
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
    diff.add_argument("--rules", type=Path, default=DEFAULT_RULES)
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
    print(inspect_module.list_rules(args.rules))
    return 0


def _cmd_show_rule(args) -> int:
    try:
        sys.stdout.write(inspect_module.show_rule(args.rules, args.rule_id))
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
    text, healthy = doctor_module.report(args.root.resolve())
    sys.stdout.write(text)
    return 0 if healthy else 1


def _cmd_stats(args) -> int:
    sys.stdout.write(inspect_module.stats(args.evidence))
    return 0


# ---------------------------------------------------------------------------
# producing a result
# ---------------------------------------------------------------------------


def _cmd_validate(args) -> int:
    problems = validate_rules(args.rules)
    if not problems:
        count = len(list(args.rules.rglob("*.yaml")))
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


def _load_rules_for(args) -> list[dict]:
    rules = [loaded.data for loaded in load_rules(args.rules)]
    profile = getattr(args, "profile", None)
    if profile and profile.exists():
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


def _cmd_evaluate(args) -> int:
    problems = validate_rules(args.rules)
    if problems:
        print(
            "refusing to evaluate: the rules do not validate. "
            "Run `m365-governance validate`.",
            file=sys.stderr,
        )
        return 2

    rules = _load_rules_for(args)
    aside = _set_aside_classes(args.profile) if args.profile else set()

    documents = _evidence_documents(args.evidence)
    runs = []
    for path in documents:
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
            return 2
        run = evaluate(rules, data)
        run.set_aside = run.resource_class in aside
        runs.append(run)

    # The shape follows what was asked for, not how many files happened to be
    # there. A directory with one document in it today and three tomorrow must
    # not change the shape of what a pipeline parses.
    if not args.evidence.is_dir():
        sys.stdout.write(_render(runs[0], args.format))
    elif args.format == "json":
        sys.stdout.write(many_to_json(runs))
    else:
        sys.stdout.write(many_to_markdown(runs))

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


def _read_run(path: Path, rules_dir: Path) -> Run:
    """A stored report, or an evidence document evaluated on the spot.

    Accepting both is not convenience. Somebody comparing two runs has one of
    each often enough: last quarter was archived as a report, this morning is
    a fresh collection, and refusing to compare them would send them to
    regenerate something they already have.
    """
    data = load_evidence(path).data
    if "results" in data:
        return Run.from_dict(data)
    if "facts" in data:
        rules = [loaded.data for loaded in load_rules(rules_dir)]
        return evaluate(rules, data)
    raise DocumentError(
        f"{path}: neither a report (no `results`) nor evidence (no `facts`)"
    )


def _cmd_report(args) -> int:
    data = load_evidence(args.report).data
    if "results" not in data:
        print(
            f"{args.report}: not a report. `report` re-renders a stored run; "
            f"to evaluate evidence use `evaluate`.",
            file=sys.stderr,
        )
        return 2
    sys.stdout.write(_render(Run.from_dict(data), args.format))
    return 0


def _cmd_diff(args) -> int:
    before = _read_run(args.before, args.rules)
    after = _read_run(args.after, args.rules)
    sys.stdout.write(diffing.to_markdown(before, after))

    if args.fail_on_regression:
        regressed = [
            c
            for c in diffing.compare(before, after)
            if c.before
            and c.after
            and c.before.outcome is Outcome.PASS
            and c.after.outcome is not Outcome.PASS
        ]
        if regressed:
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
    "report": _cmd_report,
    "diff": _cmd_diff,
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except DocumentError as exc:
        print(f"document error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"not valid JSON: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
