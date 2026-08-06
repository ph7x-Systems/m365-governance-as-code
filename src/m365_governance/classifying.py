"""What kind of list this is, from facts the product reports about it.

The collector observes and never judges, so it does not classify. It records
what SharePoint says: `IsSystemList`, `IsCatalog`, `IsApplicationList`,
`BaseTemplate`, `Hidden`. Every one of those is the product's own answer.

The classification is ours, and it is exactly one thing: an order of
precedence over those facts. That order lives here, in one function, so it
appears in a diff and can be argued with. It is not in the collector, where it
would have decided what to gather, and not in a rule, where it would have been
a claim about a tenant rather than a way of grouping one.

**Nothing is ever excluded from collection or from evaluation by this.** A
class is a label. What a profile does with the label is the next question, and
the answer there is "moves it down the report", never "drops it".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ListClass(StrEnum):
    #: SharePoint's own plumbing. Catalogs, and anything the product marks as
    #: a system list.
    SYSTEM = "system"
    #: Created by an app or a feature rather than by a person.
    APPLICATION = "application"
    #: What somebody would call a list or a library.
    CONTENT = "content"
    #: The facts needed were not collected. Never assumed to be content: a
    #: list nobody classified is a list nobody looked at.
    UNKNOWN = "unknown"


#: The facts this reads, and the property each comes from. Named here so that
#: a collector that stops emitting one is visible rather than silently
#: producing `unknown` for everything.
INPUTS = {
    "list.is_catalog": "IsCatalog",
    "list.is_system": "IsSystemList",
    "list.is_application": "IsApplicationList",
    "list.hidden": "Hidden",
    "list.base_template": "BaseTemplate",
}


@dataclass(frozen=True)
class Classification:
    kind: ListClass
    #: Which fact decided it, so a reader can disagree with the precedence
    #: rather than with the label.
    because: str


def _observed(facts: dict, block: str, name: str):
    node = (facts.get(block) or {}).get(name)
    if isinstance(node, dict) and node.get("state") == "observed":
        return node.get("value")
    return None


def classify_list(facts: dict) -> Classification:
    """Precedence, and the reason for it.

    The order below was written from the documentation and then corrected
    against a real tenant, where 23 lists disagreed with it twice. Both
    corrections are recorded here rather than quietly applied.

    **A catalog is plumbing, whatever else it is.** A catalog is a store the
    platform reads from: master pages, themes, web parts, list templates.
    Nobody puts a document in one on purpose.

    **`is_application` outranks `is_system`, and the tenant is why.** Site
    Pages and Site Assets come back with both flags set. They were provisioned
    by the platform and they hold the pages of the site, which is content
    somebody wrote. Reading `is_system` first labelled them plumbing and moved
    a site's own pages down the report. `is_application` says where a list
    came from without saying it can be ignored, which is the more useful of
    the two answers when both are true.

    **`is_system` is last of the three**, and it still catches twenty lists in
    an ordinary site: galleries, hidden taxonomy lists, app data.

    Absence of all three is `unknown`, never `content`. A list nobody
    classified is a list nobody looked at.

    ### What this cannot do

    These flags answer "who provisioned this", not "is this worth reading".
    Usually the two coincide. `App Packages`, the site collection app catalog,
    comes back as none of the three and is therefore `content`, which is
    wrong in every sense except the one that matters here: it is what the
    product says, and the alternative is matching on a title.

    Matching on a title is how a classifier starts lying in a language it was
    never tested in.
    """
    catalog = _observed(facts, "list", "is_catalog")
    system = _observed(facts, "list", "is_system")
    application = _observed(facts, "list", "is_application")

    if catalog is None and system is None and application is None:
        return Classification(
            ListClass.UNKNOWN,
            "none of is_catalog, is_system or is_application was collected",
        )
    if catalog is True:
        return Classification(ListClass.SYSTEM, "is_catalog is true")
    if application is True:
        return Classification(
            ListClass.APPLICATION,
            "is_application is true"
            + (
                ", and is_system is too: provisioned by the platform, and holding "
                "content somebody wrote"
                if system is True
                else ""
            ),
        )
    if system is True:
        return Classification(ListClass.SYSTEM, "is_system is true")
    return Classification(
        ListClass.CONTENT,
        "the product marks it as none of catalog, system or application",
    )


def classify(evidence: dict) -> Classification:
    """The class of whatever this document describes.

    Only lists are classified today. A site is not: there is no equivalent
    product fact, and inventing one from a template name would be exactly the
    guess this module exists to avoid.
    """
    if (evidence.get("resource") or {}).get("type") != "list":
        return Classification(ListClass.UNKNOWN, "only lists are classified")
    return classify_list(evidence.get("facts") or {})
