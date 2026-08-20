#!/usr/bin/env python3
"""Every card in the queue says who unblocks it and what happens next.

    python3 tools/queue-claim-check.py

WHY THIS IS A GATE AND NOT ADVICE. Rule 8 of the charter's continuation
procedure says a `nothing remains` claim is established by enumeration and
never by fatigue. As prose it is advice, and advice is what an executor at the
end of a long session is least able to follow: the claim was made twice on the
day the rule was written, and the day after, a card was reported as needing a
machine when the only thing it needed was a CI job nobody had looked for.

So the enumeration is made cheap enough to be unavoidable. Every card declares:

    authority:    repository · observation · owner · interviews
    next action:  the one thing that happens when that authority arrives

`repository` means it is ours and it is not blocked. A queue where every card
says `owner` and none says `repository` is a queue somebody should read again
before saying there is nothing to do.

**IT DOES NOT READ PROSE.** It reads two fields and a heading. Whether the next
action is the right one is a judgement no gate can make; whether somebody wrote
one down is not.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "docs", "NEXT-SLICE.md")

#: A card is named by an identifier. A heading without one is a section: the
#: queue groups cards under prose, and prose is not a unit of work.
CARD = re.compile(r"^#{2,3} .*?\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3})\b")

#: The two fields, in the queue's own formatting, `**authority:**` or plain.
AUTHORITY = re.compile(r"\*{0,2}authority:\*{0,2}\s*(\S.*)", re.IGNORECASE)
NEXT = re.compile(r"\*{0,2}next action:\*{0,2}\s*(\S.*)", re.IGNORECASE)

#: Who can unblock a card. Four, because they are four different waits: ours,
#: a run against something real, a person's decision, and a market.
AUTHORITIES = {"repository", "observation", "owner", "interviews"}


class Unclaimed(SystemExit):
    pass


def cards(text: str) -> list[tuple[str, int, str]]:
    """Each card: its id, the line it starts on, and its body."""
    lines = text.splitlines()
    starts = [
        (number, found.group(1))
        for number, line in enumerate(lines)
        if (found := CARD.match(line))
    ]
    found = []
    for index, (number, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
        found.append((name, number + 1, "\n".join(lines[number:end])))
    return found


def main() -> int:
    with open(QUEUE, encoding="utf-8") as handle:
        text = handle.read()

    found = cards(text)
    if not found:
        raise Unclaimed(
            f"{QUEUE} holds no card this gate recognises. A check that finds "
            f"nothing passes forever, which is the failure it exists to prevent."
        )

    problems: list[str] = []
    counted: dict[str, int] = {}

    for name, line, body in found:
        authority = AUTHORITY.search(body)
        action = NEXT.search(body)
        if not authority:
            problems.append(f"  {name} (line {line}): no `authority:`")
        else:
            word = authority.group(1).split()[0].strip("`*.,").lower()
            if word not in AUTHORITIES:
                problems.append(
                    f"  {name} (line {line}): authority {word!r} is not one of "
                    f"{', '.join(sorted(AUTHORITIES))}"
                )
            counted[word] = counted.get(word, 0) + 1
        if not action:
            problems.append(f"  {name} (line {line}): no `next action:`")

    if problems:
        print(
            f"\n  {len(problems)} card(s) cannot be enumerated, so this queue "
            f"may not be described as exhausted:\n",
            file=sys.stderr,
        )
        print("\n".join(problems), file=sys.stderr)
        print(
            "\n  Rule 8: `nothing remains` is established by enumeration, never "
            "by fatigue.\n  A card whose authority nobody wrote down is a card "
            "nobody can establish is\n  blocked, and the honest state for it is "
            "`not established`.\n",
            file=sys.stderr,
        )
        return 1

    ours = counted.get("repository", 0)
    summary = ", ".join(f"{count} {word}" for word, count in sorted(counted.items()))
    print(f"  ✓ {len(found)} cards, all claimed: {summary}")
    if ours:
        print(f"    {ours} of them need no external authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
