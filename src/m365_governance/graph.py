"""Reading Microsoft Graph, and nothing else.

**READ-ONLY BY CONSTRUCTION, not by policy.** No function here takes an HTTP
method. There is no parameter to set to `POST` and no branch that could reach
one: the verb is a literal inside one private function, and a test asserts that
the string `POST` does not appear in this module at all. A guard that could be
turned off by passing an argument is a convention wearing the clothes of a
constraint.

**IT NEVER CREATES AUTHENTICATION.** No consent flow, no application
registration, no secret, no certificate, no token cache. A caller supplies a
bearer token and this module spends it. That is the whole of its relationship
with identity, and it is why nothing here can widen what somebody already
granted.

**IT DOES NOT PARSE TERMINAL PROSE.** The SharePoint collector runs a
PowerShell process and reads what it printed, which is right for a collector
that wraps a module. This talks to an HTTP API, so a denial is a status code
and an unavailable area is a structured value. Neither is ever a sentence to be
matched.

WHAT IT REFUSES TO FLATTEN. An empty collection and a denied read arrive as the
same shape in a naive client: nothing. They are opposite facts about a tenant,
and this module keeps them apart all the way out — `[]` with `completed`, or no
items with `unavailable` carrying the reason. A licence a tenant does not hold,
a surface a cloud does not serve and a permission nobody granted are three more
of the same mistake, and none of them is an estate with nothing in it.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

#: The default cloud, and only the default. All four national clouds serve
#: these surfaces and none of them share an address, so the host is
#: configuration rather than a constant: a hard-coded one works everywhere the
#: author happened to test and nowhere else.
GLOBAL = "https://graph.microsoft.com"

#: Which version this engine reads. Named because `v1.0` and `beta` are
#: different contracts and a client that drifted between them would be reading
#: two products.
VERSION = "v1.0"

#: How many times a throttled request is retried before the area is reported
#: unavailable. Bounded on purpose: a collector that retried until it succeeded
#: would turn a tenant that is refusing us into a process that never ends.
RETRIES = 3

#: The longest this waits when `Retry-After` asks for longer. A service may ask
#: for minutes; a collection that honoured that silently would look hung.
MAX_WAIT_SECONDS = 30.0


class Refused(Exception):
    """The request was not made, or the answer cannot be read as Graph."""


@dataclass(frozen=True)
class Identity:
    """Who is reading, from the token itself rather than from the arguments.

    WHAT IS DELIBERATELY ABSENT: the token. This carries what the token says
    about itself and never the credential, because an identity that travelled
    with its bearer would put one into every provenance record, every log and
    every archive a report is copied into.
    """

    #: `application` or `delegated`, in the evidence contract's vocabulary.
    kind: str

    #: Which directory the SESSION is operating in, from the `tid` claim.
    #:
    #: THE ONLY HONEST SOURCE FOR THIS. Public discovery resolves which
    #: directory owns an address, which anybody can do without reaching the
    #: tenant; this is what the issuer says about the session that was actually
    #: opened. The two must never be written to one field, and this one is the
    #: one that means observed.
    observed_tenant_id: str | None

    #: Granted scopes for a delegated token, or app roles for an application
    #: one. Values only, never the token they came from.
    scopes: tuple[str, ...] = ()

    @staticmethod
    def from_token(token: str) -> Identity:
        """Read the claims. The signature is the issuer's business, not ours.

        This does not verify anything: the service that receives the token
        verifies it, and a client that pretended to would be claiming an
        authority it does not have. What it reads is what the token says about
        itself, which is exactly what belongs in provenance.
        """
        claims = _claims(token)
        # `roles` on an application token, `scp` on a delegated one. Which is
        # present is how the token says which kind it is, and it is a stronger
        # answer than anything the caller could tell us.
        roles = claims.get("roles")
        scope = claims.get("scp")
        if roles:
            kind, granted = "application", tuple(roles)
        elif scope:
            kind, granted = "delegated", tuple(str(scope).split())
        else:
            # Neither claim present. `not-established` is a real answer about
            # identity rather than a gap, and it is the vocabulary the evidence
            # contract already uses.
            kind, granted = "not-established", ()
        return Identity(
            kind=kind,
            observed_tenant_id=claims.get("tid"),
            scopes=granted,
        )


#: What a refused surface needs, by the start of its path: the least
#: privileged scope the reference records and a directory role that may read
#: it for a delegated identity.
#:
#: BY SURFACE, BECAUSE ONE SENTENCE FOR EVERY PATH WAS WRONG FOR MOST OF THEM.
#: The refusal named the Conditional Access scope whatever was asked for, so a
#: refused read of applications told its operator to request a policy
#: permission. A surface with no entry is told where the answer is recorded
#: rather than given somebody else's.
NEEDS = {
    "identity/conditionalAccess": (
        "Policy.Read.All",
        "Global Reader or Conditional Access Administrator",
    ),
    "policies/authorizationPolicy": ("Policy.Read.All", "Global Reader"),
    "applications": ("Application.Read.All", "Global Reader or Directory Readers"),
    "users": ("User.Read.All", "Global Reader or Directory Readers"),
    "groups": ("GroupMember.Read.All", "Global Reader or Directory Readers"),
}


def _needs(path: str) -> str:
    for start, (scope, role) in NEEDS.items():
        if path.lstrip("/").startswith(start):
            return (
                f"Least privilege for this surface is {scope}, and a delegated "
                f"identity additionally needs a directory role such as {role}."
            )
    return (
        "The least privilege this surface needs is recorded with its collector "
        "(the Permissions line of the command's --help); a delegated identity "
        "additionally needs a directory role that may read it."
    )


@dataclass
class Unavailable:
    """Why an area could not be read. Never an empty tenant."""

    #: One of the evidence contract's absent states, so a consumer reads one
    #: vocabulary rather than learning a second one for Graph.
    state: str
    detail: str

    @staticmethod
    def of(
        status: int,
        path: str,
        body: str = "",
        headers: dict[str, str] | None = None,
    ) -> Unavailable:
        """What a status code means about a tenant, which is usually nothing.

        THE DISTINCTION THIS EXISTS FOR. `403` and an empty collection produce
        the same absence downstream unless something says which happened. One
        is a fact about permission and the other is a fact about the estate,
        and a rule over the first must answer `unknown` while a rule over the
        second may decide.
        """
        detail = ((body or "").strip()[:400] + _correlation(headers)).strip()
        if status == 401:
            # NOT `permission-denied`, and the difference is not cosmetic. A
            # `401` says the session is not valid -- expired, issued for another
            # audience, never established -- and a `403` says a valid session
            # was refused this surface. Reading the first as the second sends
            # somebody to request a Graph permission when what they needed was
            # to sign in again.
            #
            # `missing` because the evidence contract has four absent states and
            # none of them means "not authenticated". Recorded as a contract gap
            # in the slice audit rather than smuggled into the nearest word.
            return Unavailable(
                "missing",
                "the session is not valid for Microsoft Graph: expired, issued "
                "for another audience, or never established. This is not a "
                "permission problem and says nothing about the tenant. " + detail,
            )
        if status == 403:
            return Unavailable(
                "permission-denied",
                "authenticated and not permitted to read "
                f"{path}. {_needs(path)} " + detail,
            )
        if status == 404:
            return Unavailable(
                "not-supported",
                f"{path} does not exist in this cloud or API version, which is "
                "not the same as a tenant having none of it. " + detail,
            )
        if status == 429:
            return Unavailable(
                "partial",
                f"throttled while reading {path}, and the retry budget was "
                "exhausted. What was read before that is kept. " + detail,
            )
        return Unavailable(
            "missing",
            f"Microsoft Graph answered {status} for {path}. " + detail,
        )


@dataclass
class Page:
    """One answer: what it carried, and where the next one is."""

    items: list[dict[str, Any]] = field(default_factory=list)
    next_link: str | None = None


@dataclass
class Read:
    """Everything one area produced, and whether it is complete."""

    path: str
    items: list[dict[str, Any]] = field(default_factory=list)
    unavailable: Unavailable | None = None

    @property
    def complete(self) -> bool:
        """True only when the whole collection was read.

        An empty collection is complete: the tenant has none of that object,
        which is an answer. A denied read is not, and the difference is the
        point.
        """
        return self.unavailable is None


#: What a transport does: take a URL and a bearer token, return status, body
#: and headers. Injected so a test can answer without a network, and typed so
#: that NOTHING IN THE SIGNATURE CAN CARRY A VERB.
Transport = Callable[[str, str], tuple[int, str, dict[str, str]]]


class GraphReader:
    """A read-only window onto Microsoft Graph.

    The whole class offers two operations, `read` and `page`, and neither takes
    a method, a body or headers. There is no way to reach a mutation from here
    that does not involve editing this file, which is the difference between a
    constraint and a rule somebody remembers.
    """

    def __init__(
        self,
        token: str,
        *,
        endpoint: str = GLOBAL,
        version: str = VERSION,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not token:
            raise Refused(
                "no token was supplied. This reader never acquires one: it "
                "spends what a caller already holds, which is why it cannot "
                "widen anybody's consent."
            )
        self._token = token
        self._base = f"{endpoint.rstrip('/')}/{version}"
        self._transport = transport or _https
        self._sleep = sleep
        self.identity = Identity.from_token(token)
        self.source_api = f"Microsoft Graph {version}"

    @staticmethod
    def _encoded(path: str) -> str:
        """A path with its query encoded, because OData filters have spaces in.

        `$filter=roleDefinitionId eq '62e9...'` is what Microsoft documents and
        what a reader writes. It is also not a legal request target, and Python
        refuses to send it: `URL can't contain control characters ... found at
        least ' '`. So the slice that reads the directory's Global
        Administrators could never have collected from any tenant, and no test
        found it because none of them makes a request.

        Only the query is touched, and `safe` keeps every character OData gives
        meaning to -- `$`, `=`, `&`, `,`, `'` and the parentheses of a function
        segment. Encoding those would change the request rather than transport
        it, which is the failure this is fixing in the other direction.
        """
        head, sep, query = path.partition("?")
        if not sep:
            return head
        return head + "?" + urllib.parse.quote(query, safe="$=&,'()/:*")

    def read(self, path: str) -> Read:
        """Every item of a collection, following the service's own next links.

        `@odata.nextLink` is followed and never constructed. A client that
        built its own page URLs would be deciding how the service paginates,
        and would keep working until the day the service changed its mind.
        """
        url = f"{self._base}/{self._encoded(path).lstrip('/')}"
        found: list[dict[str, Any]] = []
        seen: set[str] = set()

        while url:
            if url in seen:
                # A service that pointed back at a page already read would loop
                # this forever. Reported rather than survived: a collection that
                # cannot terminate is not a collection.
                return Read(
                    path,
                    found,
                    Unavailable(
                        "partial",
                        f"the next link for {path} repeated a page already "
                        "read, so the collection was stopped.",
                    ),
                )
            seen.add(url)

            outcome = self._once(url, path)
            if isinstance(outcome, Unavailable):
                # What was read before the refusal is kept. A partial read of a
                # tenant is worth exactly what it read, and discarding it would
                # be the collapse the collection states exist to end.
                return Read(path, found, outcome)

            found.extend(outcome.items)
            url = outcome.next_link or ""

        return Read(path, found)

    def one(self, path: str) -> Read:
        """A single resource rather than a collection.

        Security Defaults is one object, not a list, and wrapping it in a list
        of one keeps every consumer reading a single shape.
        """
        outcome = self._once(
            f"{self._base}/{self._encoded(path).lstrip('/')}", path, single=True
        )
        if isinstance(outcome, Unavailable):
            return Read(path, [], outcome)
        return Read(path, outcome.items)

    def _once(self, url: str, path: str, single: bool = False) -> Page | Unavailable:
        """One request, with a bounded retry on throttling."""
        for attempt in range(RETRIES + 1):
            status, body, headers = self._transport(url, self._token)

            if status == 200:
                return _page(body, path, single)

            if status == 429 and attempt < RETRIES:
                self._sleep(_retry_after(headers))
                continue

            return Unavailable.of(status, path, body, headers)

        return Unavailable.of(429, path, "", headers)


def _page(body: str, path: str, single: bool) -> Page | Unavailable:
    try:
        document = json.loads(body)
    except json.JSONDecodeError as problem:
        return Unavailable(
            "invalid",
            f"Microsoft Graph answered 200 for {path} with something that is "
            f"not JSON: {problem}",
        )
    if not isinstance(document, dict):
        return Unavailable("invalid", f"{path} answered with {type(document).__name__}")

    if single:
        return Page([document])

    value = document.get("value")
    if not isinstance(value, list):
        return Unavailable(
            "invalid",
            f"{path} answered 200 without a `value` collection, so this engine "
            "cannot tell an empty tenant from a shape it does not understand.",
        )
    items = [x for x in value if isinstance(x, dict)]
    return Page(items, document.get("@odata.nextLink"))


#: What Microsoft calls the identifier of a request, in the two header names it
#: uses. Read case-insensitively because a header name is not case-sensitive and
#: a client that matched one casing works until the day a proxy changes it.
CORRELATION = ("request-id", "client-request-id", "x-ms-ags-diagnostic", "date")


def _correlation(headers: dict[str, str] | None) -> str:
    """The identifiers Microsoft support asks for, kept with the refusal.

    A REFUSAL IS EVIDENCE, AND EVIDENCE THAT CANNOT BE TRACED IS AN ANECDOTE.
    A `403` that a tenant administrator disputes is settled by Microsoft
    looking the request up, and they look it up by these. Without them the
    conversation is "our tool says it was denied" against "our portal says the
    permission is granted", and there is no third thing to consult.

    They are recorded on the refusal rather than in a log, because the log is
    on the machine that ran the collection and the refusal is what travels into
    the evidence, the report and the archive somebody opens six months later.
    """
    if not headers:
        return ""
    found = {}
    for name, value in headers.items():
        key = name.strip().lower()
        if key in CORRELATION and value:
            found[key] = value
    if not found:
        return ""
    return " [" + ", ".join(f"{k}: {v}" for k, v in sorted(found.items())) + "]"


def _retry_after(headers: dict[str, str]) -> float:
    """What the service asked for, bounded by what a person will wait through."""
    raw = headers.get("Retry-After") or headers.get("retry-after") or ""
    try:
        asked = float(raw)
    except ValueError:
        asked = 1.0
    return max(0.0, min(asked, MAX_WAIT_SECONDS))


def _claims(token: str) -> dict[str, Any]:
    """The middle segment of a JWT, decoded. Never verified here."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return {}


def _https(url: str, token: str) -> tuple[int, str, dict[str, str]]:
    """The only place a request leaves this process.

    THE METHOD IS A LITERAL AND THERE IS NO PARAMETER FOR IT. `urlopen` on a
    Request with no data sends GET; passing `data` is what makes it a POST, and
    nothing here has a `data` to pass. That is the structural half of read-only,
    and the test that greps this module for mutating verbs is the other.
    """
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:  # noqa: S310
            return (
                answer.status,
                answer.read().decode("utf-8", errors="replace"),
                dict(answer.headers),
            )
    except urllib.error.HTTPError as refused:
        return (
            refused.code,
            refused.read().decode("utf-8", errors="replace"),
            dict(refused.headers or {}),
        )
    except urllib.error.URLError as unreachable:
        raise Refused(
            f"Microsoft Graph could not be reached: {unreachable.reason}"
        ) from unreachable


def iter_reads(
    reader: GraphReader, paths: dict[str, str]
) -> Iterator[tuple[str, Read]]:
    """Read several areas, keeping each one's outcome separate.

    One area failing never removes another's result, and never turns the
    collection as a whole into a failure: a tenant where policies read and
    named locations were denied produced evidence worth the policies.
    """
    for area, path in paths.items():
        yield area, reader.read(path)
