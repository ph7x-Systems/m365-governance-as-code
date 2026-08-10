"""Where the product's own content lives, and where the user's does.

**A clean installation is the reference environment. The development
repository is a convenience, not the execution model.**

Nothing here resolves a path relative to this file or to the working
directory. Both were tried and both were wrong, in different ways:

- `Path("rules")` fails wherever you stand, which at least fails loudly;
- `Path(__file__).resolve().parents[2] / "collectors"` looks relocatable
  because it is anchored to `__file__` rather than to the working directory,
  and resolves to the repository root from `src/` and to
  `lib/python3.x/collectors` from site-packages. It points somewhere plausible
  that does not exist.

`importlib.resources` asks the import system where the package actually is,
which is the only question with a correct answer in both.

### Three rules, and they are decisions rather than conveniences

**1. A packaged rule changes only with a release.** That is the point of it. A
rule is part of the observable behaviour of this product, so changing one
changes what the product says, and it should require the same ceremony as
changing any other behaviour.

**2. External content declares itself.** A report says whether a rule came
from the package or from a path somebody supplied, because a finding produced
by rules nobody can identify is not reproducible.

**3. There is never an implicit merge.** Either the packaged set, complete, or
the set the user supplied, complete. "Defaults plus a few of mine" produces a
rule set that exists only in the memory of whoever ran the command, and two
runs of the same version stop meaning the same thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

#: The subdirectories of `m365_governance.data`, and what each holds.
BUNDLED = ("rules", "profiles", "schemas", "collectors", "fixtures", "generated")


@dataclass(frozen=True)
class Source:
    """A directory or file, and where it came from.

    Carried into the report rather than resolved and forgotten. `origin` is
    the second of the three rules above: a reader must be able to tell whether
    a finding came from rules that ship with the version they are running.
    """

    path: Path
    #: `package` or `external`. Never inferred from the path: it is decided by
    #: whether the user supplied one.
    origin: str

    @property
    def is_packaged(self) -> bool:
        return self.origin == "package"

    def describe(self) -> str:
        if self.is_packaged:
            return "shipped with this version"
        return f"supplied by the caller: {self.path}"


def packaged(name: str) -> Path:
    """The filesystem path of one bundled directory.

    `files()` returns a `Traversable`, which is not always a real path: a
    package imported from a zip has no directory to point at. Every supported
    installation is a normal wheel unpacked onto a filesystem, and the
    collector has to be handed to `pwsh` as a real path, so this converts and
    says so rather than pretending to support the other case.
    """
    if name not in BUNDLED:
        raise KeyError(f"{name} is not bundled; expected one of {', '.join(BUNDLED)}")
    root = files("m365_governance.data").joinpath(name)
    try:
        return Path(str(root))
    except TypeError as exc:  # pragma: no cover - not reachable from a wheel
        raise RuntimeError(
            "the package content is not on a filesystem. This happens when "
            "m365_governance is imported from a zip, which is not supported: "
            "the collector must be handed to PowerShell as a real path."
        ) from exc


def resolve(name: str, override: Path | None) -> Source:
    """The packaged content, or exactly what the caller asked for.

    Never both. `override` replaces; it does not add. See rule 3.
    """
    if override is not None:
        return Source(path=Path(override), origin="external")
    return Source(path=packaged(name), origin="package")


def missing() -> list[str]:
    """Bundled directories the installed package does not actually contain.

    Present so `doctor` can report a broken installation rather than a broken
    tenant. An empty list here is what the clean-install gate proves.
    """
    absent = []
    for name in BUNDLED:
        try:
            if not packaged(name).is_dir():
                absent.append(name)
        except (RuntimeError, ModuleNotFoundError, FileNotFoundError):
            absent.append(name)
    return absent
