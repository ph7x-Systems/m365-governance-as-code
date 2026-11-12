#!/usr/bin/env python3
"""Write docs/COMMAND-REFERENCE.json, or check that it is current.

The file is what a documentation site reads to list the commands: one entry
per command with what it reads, the permissions recorded for it, the rules it
feeds and how far it has been proved. It is derived, never edited.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from m365_governance import reference  # noqa: E402

PUBLISHED = ROOT / "docs" / "COMMAND-REFERENCE.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = json.dumps(reference.build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if not PUBLISHED.exists() or PUBLISHED.read_text(encoding="utf-8") != current:
            print(
                "docs/COMMAND-REFERENCE.json is not current. "
                "Run tools/command-reference.py."
            )
            return 1
        return 0
    PUBLISHED.write_text(current, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
