"""The canonical form, in one place.

THE CANONICAL FORM IS PART OF THE CONTRACT, not an implementation detail,
because a consumer has to reproduce it exactly to verify anything:

    keys sorted, byte order
    no whitespace between tokens
    UTF-8, with nothing escaped that does not have to be

That last line was learned rather than chosen. The first version left Python's
default `ensure_ascii=True` in place, and a consumer using the ordinary .NET
encoder escaped apostrophes as \\u0027 while Python wrote them raw. Ten
apostrophes in one run set were enough for two correct implementations of "the
same JSON" to produce different digests.

WHY IT IS A MODULE. It was a private function inside the assessment, and it is
now used by two documents that both publish a digest a recipient recomputes. A
second copy of these four lines would be a second definition of the canonical
form, and the two would agree until whichever one nobody was looking at drifted
— which is the same failure the contract versions exist to make impossible.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Named in the documents that publish a digest, so a consumer verifying one
#: does not have to know which engine version wrote it to know the algorithm.
ALGORITHM = "sha256"


def encode(value: Any) -> bytes:
    """The bytes a digest is taken over."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    """A digest of the value in the contract's canonical form."""
    return hashlib.sha256(encode(value)).hexdigest()
