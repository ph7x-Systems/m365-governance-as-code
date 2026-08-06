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

    A catalog is checked first because a catalog is always plumbing, whatever
    else it also is: Style Library and Form Templates are catalogs that are
    not marked as system lists, and reading them as content is how three of
    eight lists in a real tenant became noise.

    `IsSystemList` comes next because it is the product saying so outright.

    `IsApplicationList` is last of the three because a list can be created by
    an app and still hold content somebody cares about. Calling it
    `application` says where it came from, not that it can be ignored.

    Absence of all three is `unknown`, never `content`. A list nobody
    classified is a list nobody looked at, and the difference matters for the
    same reason it matters everywhere else here.
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
    if system is True:
        return Classification(ListClass.SYSTEM, "is_system is true")
    if application is True:
        return Classification(ListClass.APPLICATION, "is_application is true")
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
