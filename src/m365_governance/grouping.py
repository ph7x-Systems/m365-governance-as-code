"""The command line by group, over the commands that already exist.

`m365g spo site list` and `m365g collect sites` are one command. The grouped
name is how a person finds it — by the service, then the thing, then what to
do with it — and the flat name is what scripts and consumers already invoke
(docs/CLI.md). This module owns the correspondence and nothing else: a grouped
path is rewritten to the flat command before the parser sees it, so there is
one parser, one handler and one behaviour per command, and no second
implementation to drift from the first.

NOTHING HERE INVENTS A CAPABILITY. Every path leads to a command or a
collection this engine already has, and a test holds the table to the parser
and to the collector's own registry in both directions: a collection with no
path fails, and so does a path to something that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    name: str
    says: str
    #: Path under the group -> the flat command line it stands for.
    paths: dict[tuple[str, ...], tuple[str, ...]]


def _collect(slice_name: str) -> tuple[str, ...]:
    return ("collect", slice_name)


GROUPS: tuple[Group, ...] = (
    Group(
        "spo",
        "SharePoint Online: what a tenant and its sites are set to",
        {
            ("site", "list"): _collect("sites"),
            ("hub", "list"): _collect("hubs"),
            ("site", "admins"): _collect("sites-owners"),
            ("owner", "list"): _collect("owners"),
            ("sharing", "get"): _collect("sharing"),
            ("sharing", "list"): _collect("sites-sharing"),
            ("tenant", "sharing", "get"): _collect("tenant-sharing"),
            ("permission", "list"): _collect("permissions"),
            ("activity", "get"): _collect("activity"),
            ("classification", "get"): _collect("classification"),
            ("modernity", "get"): _collect("modernity"),
            ("customization", "get"): _collect("customization"),
            ("spfx", "list"): _collect("spfx"),
            ("agent", "list"): _collect("agents"),
            ("brandcenter", "get"): _collect("brand-center"),
        },
    ),
    Group(
        "entra",
        "Microsoft Entra: sign-in policy, tenant defaults and licences",
        {
            ("ca", "list"): _collect("conditional-access"),
            ("guest", "list"): _collect("guests"),
            ("app", "list"): _collect("applications"),
            ("group", "list"): _collect("groups"),
            ("tenant", "governance", "get"): _collect("tenant-governance"),
            ("license", "list"): _collect("licensing"),
        },
    ),
    Group(
        "exo",
        "Exchange Online: whether mail can leave automatically",
        {
            ("forwarding", "get"): _collect("forwarding"),
        },
    ),
    Group(
        "evidence",
        "collect evidence, and look at what a collection managed to see",
        {
            ("collect",): ("collect",),
            ("stats",): ("stats",),
            ("evaluate",): ("evaluate",),
        },
    ),
    Group(
        "governance",
        "from a target to a result somebody else can check",
        {
            ("run",): ("run",),
            ("assess",): ("assess",),
            ("verify",): ("verify",),
            ("report",): ("report",),
            ("diff",): ("diff",),
            ("inspect",): ("inspect",),
        },
    ),
    Group(
        "rule",
        "the rules: what each claims, and what an outcome means",
        {
            ("list",): ("list-rules",),
            ("show",): ("show-rule",),
            ("get",): ("show-rule",),
            ("validate",): ("validate",),
            ("explain",): ("explain",),
        },
    ),
    Group(
        "migration",
        "what a move actually moved, from a read before and one after",
        {
            ("read",): ("migration-read",),
            ("verify",): ("migration-verify",),
        },
    ),
    Group(
        "engine",
        "this installation: what it needs, what it promises, what it publishes",
        {
            ("doctor",): ("doctor",),
            ("setup",): ("setup",),
            ("capabilities",): ("capabilities",),
            ("contracts",): ("contracts",),
        },
    ),
)

BY_NAME = {group.name: group for group in GROUPS}


def regroup(argv: list[str]) -> list[str]:
    """Rewrite a grouped path to the flat command it stands for.

    The longest path wins, so `spo tenant sharing get` is not read as a
    shorter one with arguments. Anything that is not a complete grouped path
    is returned untouched: a flat command, a group named on its own, or a
    path that does not exist, each of which the parser answers for itself.
    """
    if not argv or argv[0] not in BY_NAME:
        return argv
    group = BY_NAME[argv[0]]
    for path in sorted(group.paths, key=len, reverse=True):
        if tuple(argv[1 : 1 + len(path)]) == path:
            return [*group.paths[path], *argv[1 + len(path) :]]
    return argv


def listing(group: Group, command: str, describe) -> str:
    """What a group contains, for a person. `describe` says what a flat command does."""
    rows = [
        (f"{command} {group.name} {' '.join(path)}", describe(flat))
        for path, flat in group.paths.items()
    ]
    width = max(len(row[0]) for row in rows)
    lines = [f"{group.says}.", ""]
    lines += [f"  {name.ljust(width)}  {what}" for name, what in rows]
    lines += [
        "",
        f"Add --help to any of them. Each is the same command as its earlier "
        f"name, which keeps working: `{command} {group.name} "
        f"{' '.join(next(iter(group.paths)))}` is `{command} "
        f"{' '.join(next(iter(group.paths.values())))}`.",
    ]
    return "\n".join(lines)
