"""Microsoft 365 governance checks that show their work."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

# READ, NOT WRITTEN DOWN TWICE.
#
# This was `__version__ = "1.0.0b1"`, a literal beside the one in
# pyproject.toml. Releasing 1.0.0b2 bumped the packaging version and left this
# one behind, so the wheel was named 1.0.0b2 and `--version` answered 1.0.0b1.
#
# The naming half is cosmetic. The other half is not: this value travels into
# every assessment as `engine_version`, so an assessment produced by one build
# would state that a different build decided it. In an engine whose whole claim
# is that a conclusion can be traced back to what produced it, a version that
# lies is not a typo.
#
# The distribution metadata is the single source, and it comes from
# pyproject.toml. The fallback covers a source tree that was never installed,
# where there is no distribution to ask.
try:
    __version__ = _version("m365-governance-as-code")
except PackageNotFoundError:  # pragma: no cover - only outside an installation
    __version__ = "0.0.0+unknown"
