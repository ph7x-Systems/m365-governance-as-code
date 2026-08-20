"""The target, written down once, so that a run is not retyped.

WHY THIS EXISTS. A collection is one slice at a time, so a tenant assessed
across ten slices was ten commands, each repeating the application registration
and an address. An audit on 2026-08-20 counted the same two arguments written
eleven times to reach a first report. Every repetition is a chance to point one
of them somewhere else, and nothing downstream would notice.

WHY IT IS NOT AN ENVIRONMENT VARIABLE. PnP.PowerShell reads an ambient client
id, and this collector deliberately refuses to: evidence has to be able to name
the identity that observed it, and a value read from the environment of a shell
nobody kept is one nobody can name afterwards. A file at a path is the opposite
of ambient. It has a name, it is read once, and the command says which one it
read -- so the objection that closed the environment variable is answered
rather than worked around.

NO SECRET IS EVER READ FROM HERE, AND THAT IS ENFORCED RATHER THAN ASSUMED. A
project file is committed, copied into a ticket and pasted into a chat, and the
first person to put a certificate password in one would find out later. A key
that names a secret is refused by name, with the file and the line, instead of
being quietly ignored -- ignoring it would leave the secret sitting in the file
while the run appeared to work.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .loader import DocumentError

#: What the file is called. One name, looked for by that name, because a
#: product that accepted four spellings would have four ways to be surprised by
#: which one was read.
NAME = "m365-governance.toml"

#: Keys that would hold a credential. Refused by name wherever they appear.
#: The list is what somebody would plausibly type, not what this engine
#: supports: the point is to catch the attempt, and an unsupported key that was
#: silently ignored would leave the secret in the file.
SECRETS = frozenset(
    {
        "certificate_password",
        "client_secret",
        "password",
        "secret",
        "token",
        "app_secret",
    }
)

#: What may be written, per table. Anything else is a mistake worth naming: a
#: misspelled key that was ignored would leave a run using a default while the
#: file on disk said otherwise.
FIELDS: dict[str, frozenset[str]] = {
    "target": frozenset({"tenant_url", "site_url"}),
    "identity": frozenset(
        {
            "client_id",
            "tenant_id",
            "certificate_path",
            "certificate_password_env",
            "device_login",
        }
    ),
    "assess": frozenset({"profile", "rules"}),
}

#: Which command-line destination each field fills. One mapping, so that a
#: field cannot mean one thing here and another in the parser.
DESTINATIONS: dict[tuple[str, str], str] = {
    ("target", "tenant_url"): "tenant_url",
    ("target", "site_url"): "site_url",
    ("identity", "client_id"): "client_id",
    ("identity", "tenant_id"): "tenant_id",
    ("identity", "certificate_path"): "certificate_path",
    ("identity", "certificate_password_env"): "certificate_password_env",
    ("identity", "device_login"): "device_login",
    ("assess", "profile"): "profile",
    ("assess", "rules"): "rules",
}

#: Destinations the parser holds as paths. A string from a file has to arrive
#: as the same type the command line produces, or the two sources would behave
#: differently in the code that reads them.
PATHS = frozenset({"certificate_path", "profile", "rules"})


class Project:
    """One project file, read. Never a merge of several."""

    def __init__(self, path: Path, values: dict[str, Any]) -> None:
        self.path = path
        self.values = values

    def __bool__(self) -> bool:
        return bool(self.values)

    def apply(self, args) -> list[str]:
        """Fill what the command line did not say, and report what was filled.

        THE COMMAND LINE ALWAYS WINS. A file that could override an argument
        somebody typed would make the same command mean two things in two
        directories, and the person reading the terminal would have no way to
        tell which had happened.

        Returned rather than printed, because what a caller does with it
        differs: a person is told, and a `--format json` consumer is not
        interrupted mid-document.
        """
        filled = []
        for destination, value in self.values.items():
            if not hasattr(args, destination):
                continue
            current = getattr(args, destination)
            # False is what `store_true` leaves behind when the flag is absent,
            # and it is indistinguishable from a flag deliberately not passed.
            # A file may turn it on; nothing here can turn one off.
            if current not in (None, False):
                continue
            if destination in PATHS:
                value = Path(value)
            setattr(args, destination, value)
            filled.append(destination)
        return sorted(filled)


def find(start: Path | None = None) -> Path | None:
    """The nearest project file, from here upwards. None where there is none.

    Upwards because a repository has one target and many directories, and a
    person standing in a subdirectory means the same tenant they meant one
    level up. Which file was used is always reported: a search that found a
    file the caller did not know about would be exactly the ambient
    configuration this file exists instead of.
    """
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / NAME
        if candidate.is_file():
            return candidate
    return None


def load(path: Path) -> Project:
    """One project file, validated. Refusals name the key and the file."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DocumentError(f"{path}: no such file") from None
    except tomllib.TOMLDecodeError as exc:
        raise DocumentError(f"{path}: not valid TOML: {exc}") from None

    _refuse_secrets(path, raw)

    values: dict[str, Any] = {}
    for table, contents in raw.items():
        if table not in FIELDS:
            raise DocumentError(
                f"{path}: [{table}] is not a section this file has. "
                f"Known sections: {', '.join(sorted(FIELDS))}."
            )
        if not isinstance(contents, dict):
            raise DocumentError(
                f"{path}: [{table}] must be a section, and it holds a value. "
                f"Every setting belongs to one of: {', '.join(sorted(FIELDS))}."
            )
        for key, value in contents.items():
            if key not in FIELDS[table]:
                raise DocumentError(
                    f"{path}: [{table}] has no setting called {key!r}. "
                    f"In this section: {', '.join(sorted(FIELDS[table]))}."
                )
            values[DESTINATIONS[(table, key)]] = value
    return Project(path, values)


def _refuse_secrets(path: Path, raw: dict[str, Any]) -> None:
    """A credential in a project file is refused, not ignored.

    Ignoring it would leave the secret in a file somebody commits, while the
    run carried on and looked correct. The refusal names the key so that the
    person removing it knows which line to delete, and names the option that
    does the job properly.
    """
    for table, contents in raw.items():
        if not isinstance(contents, dict):
            continue
        for key in contents:
            if key.lower() in SECRETS:
                raise DocumentError(
                    f"{path}: [{table}] holds {key!r}, and this file never "
                    f"carries a credential: it is committed, copied into "
                    f"tickets and pasted into chats. Put the password in an "
                    f"environment variable and name the variable with "
                    f"certificate_password_env, which passes the name and "
                    f"never the value."
                )
