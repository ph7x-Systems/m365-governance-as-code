"""The Microsoft 365 surfaces this engine claims to govern, observed or not.

WHY THIS IS NOT A LIST OF COLLECTORS. A catalogue built from what exists
answers "what did we write", and every entry in it is something that works.
Read as a map of Microsoft 365 it is a lie of omission: a reader sees ten
SharePoint capabilities and concludes the product covers Microsoft 365, because
nothing on the page says Exchange was never started. The domains with no
collector are the ones that make this document true, and they are the reason it
is a separate registry rather than a grouping of `SLICES`.

WHAT A DOMAIN STATE IS AND IS NOT. It is not a score, an average or a grade:
charter `D5` refuses those, and a domain holding one proven surface and one
unproven one does not become half-proven. Each domain publishes the surfaces it
has, each surface publishes what a tenant established about IT, and the domain
additionally names its WEAKEST surface, which is a fact about a particular
surface rather than a number computed over several. `not-started` is the one
state a domain carries in its own right, and it means exactly one thing: this
engine has no acquisition surface here at all.

THE ENTRY RULE. A domain arrives at `not-started`, gains surfaces at `none`,
and moves through `provider-only`, `partial` and `full` as live proof arrives.
Nothing is ever declared supported on the strength of the code existing. This
is written here because it was learnt three times: `spfx` published
`live-validated` for a branch no real catalog ever produced, `licensing` was
one commit away from publishing a state that was false, and `conditional-access`
counted a transport read as a slice read.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    """One Microsoft 365 surface, and what governing it would mean."""

    key: str
    title: str

    #: The question an organisation has about this surface. It is written for
    #: every domain, including the ones nothing reads yet, because the question
    #: is what makes an absence legible: "Exchange: not started" says little,
    #: and "who can read this mailbox, and where does its mail go: not started"
    #: says what is missing.
    question: str

    #: What acquiring evidence here would require, in Microsoft's terms. Named
    #: for unstarted domains too: an acquisition surface nobody has looked for
    #: is a different kind of absent from one that does not exist.
    acquisition: str

    #: What this engine refuses to conclude in this domain even when it can
    #: observe it, and why. Empty where nothing has been decided yet.
    authority: str = ""


#: Ordered as the programme intends to reach them, not alphabetically: the
#: order is a statement about sequencing and is read as one.
DOMAINS: tuple[Domain, ...] = (
    Domain(
        key="sharepoint",
        title="SharePoint",
        question=(
            "how is this site built, who administers it, what does it permit, "
            "and what can execute inside it"
        ),
        acquisition="PnP.PowerShell against the site and the admin centre",
        authority=(
            "Microsoft documents the customization controls as reaching less "
            "than their names suggest, so the page-execution surfaces are "
            "collected and no rule decides from them"
        ),
    ),
    Domain(
        key="entra",
        title="Identity and access",
        question=(
            "who can sign in, under what conditions, and what may act on their behalf"
        ),
        acquisition="Microsoft Graph, with a token this engine never acquires",
        authority=(
            "Microsoft publishes no normative conclusion about which "
            "Conditional Access policies an organisation should have, so the "
            "inventory is collected and no rule decides from it"
        ),
    ),
    Domain(
        key="licensing",
        title="Licensing and commerce",
        question=(
            "what is assigned, whether its use can be attributed to anybody, "
            "and what depends on it"
        ),
        acquisition="Microsoft Graph: the directory and the reporting endpoints",
        authority=(
            "removing an assignment needs evidence of use AND of dependency; "
            "this reads the first at best, so it recommends nothing"
        ),
    ),
    Domain(
        key="agents",
        title="Agents and Copilot",
        question=(
            "which agents exist, what they were given to read, and who may reach them"
        ),
        acquisition=(
            "enumeration of the files one publication surface writes; the "
            "builder surfaces have no read this engine has found"
        ),
        authority=(
            "an inventory surface defines a population and does not define "
            "existence outside it, so a count is published with its population "
            "and no rule reads it"
        ),
    ),
    Domain(
        key="brand-center",
        title="Brand Center and organisation assets",
        question=(
            "which site is the authority for an organisation's fonts, themes "
            "and images, and how far does what it publishes actually reach"
        ),
        acquisition=(
            "the organisation asset libraries and the site that owns them; the "
            "distribution boundary has no read established"
        ),
    ),
    Domain(
        key="teams",
        title="Teams",
        question=(
            "who is in this team, who from outside can reach it, and what apps "
            "and policies apply to the people in it"
        ),
        acquisition="Microsoft Graph and the Teams administration surfaces",
    ),
    Domain(
        key="exchange",
        title="Exchange",
        question=(
            "who can read this mailbox, where does its mail go, and what is "
            "shared outside the organisation"
        ),
        acquisition=(
            "Exchange Online PowerShell; a different session and a different "
            "identity from everything this engine collects today"
        ),
    ),
    Domain(
        key="onedrive",
        title="OneDrive",
        question=(
            "whose personal site is this, what does it share outside the "
            "organisation, and what happens to it when they leave"
        ),
        acquisition="the SharePoint admin surfaces this engine already opens",
    ),
    Domain(
        key="purview",
        title="Purview and compliance",
        question=(
            "what is labelled, what is retained, what is prevented from "
            "leaving, and what is recorded about any of it"
        ),
        acquisition="Microsoft Graph and the compliance administration surfaces",
    ),
    Domain(
        key="defender",
        title="Defender and security",
        question=(
            "what is inspected before it reaches somebody, and what is done "
            "when it is not safe"
        ),
        acquisition="the Defender administration surfaces, where an API permits",
    ),
    Domain(
        key="power-platform",
        title="Power Platform",
        question=(
            "which environments exist, what may connect to what inside them, "
            "and who owns what runs there"
        ),
        acquisition="the Power Platform administration surfaces",
    ),
    Domain(
        key="intune",
        title="Devices",
        question=(
            "which devices are enrolled, what is required of them, and what is "
            "true of the ones that are not"
        ),
        acquisition="Microsoft Graph device management, if it proves worth adding",
    ),
)

BY_KEY = {domain.key: domain for domain in DOMAINS}

#: The one state a domain carries in its own right. Every other state on the
#: matrix belongs to a surface.
NOT_STARTED = "not-started"
