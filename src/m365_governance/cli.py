"""Command line.

Two commands, and neither writes anything to a tenant. There is no write path
in this system: remediation is text in a rule, addressed to a person.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .engine import evaluate
from .loader import DocumentError, load_evidence, load_profile, load_rules
from .reporting import to_json, to_markdown
from .results import Outcome
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
        "--format", choices=("markdown", "json"), default="markdown"
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
    return parser


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


def _cmd_evaluate(args) -> int:
    problems = validate_rules(args.rules)
    if problems:
        print(
            "refusing to evaluate: the rules do not validate. "
            "Run `m365-governance validate`.",
            file=sys.stderr,
        )
        return 2

    evidence = load_evidence(args.evidence)
    evidence_problems = validate_evidence_document(evidence.data, str(evidence.path))
    if evidence_problems:
        for problem in evidence_problems:
            print(problem, file=sys.stderr)
        print(
            "\nrefusing to evaluate: the evidence does not match the schema. "
            "This is a defect in the collector, not a finding about the resource.",
            file=sys.stderr,
        )
        return 2

    rules = [loaded.data for loaded in load_rules(args.rules)]
    if args.profile.exists():
        selected = load_profile(args.profile).get("rules")
        if selected:
            rules = [r for r in rules if r["id"] in selected]

    run = evaluate(rules, evidence.data)
    output = to_json(run) if args.format == "json" else to_markdown(run)
    sys.stdout.write(output)

    counts = run.counts()
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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            return _cmd_validate(args)
        return _cmd_evaluate(args)
    except DocumentError as exc:
        print(f"document error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
