"""The product's own content, shipped inside the package.

Rules, profiles, schemas, collectors and fixtures live here rather than at the
root of the repository, and the reason is the second governing principle in
docs/PRODUCT-STRATEGY.md: **a clean installation is the reference environment,
and the development repository is a convenience.**

Before this, `pip install` produced a command-line tool with none of its own
content. Every path resolved against the working directory or against the
`src/` layout, so nine of ten commands failed the moment somebody ran them
from anywhere that was not a checkout. Every test in the suite agreed the
product worked, because every test ran from the repository root.

Reached through `importlib.resources`, never through a path relative to this
file. See `resources.py` for why that distinction is the whole fix.
"""
