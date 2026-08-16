# Releasing

Written down because it lived in a conversation once, and a procedure that
lives in a conversation is a procedure the next person reconstructs by
guessing.

## The model

Publishing uses PyPI **trusted publishing**. GitHub presents an OIDC identity,
PyPI checks it came from this repository, this workflow file and this
environment, and mints a token that lives for one upload.

**There is no API token, no password and no secret**, on either side. Nothing
to store, rotate or leak.

The PyPI side is registered once, under Account settings, publishing:

| Field | Value |
| --- | --- |
| PyPI Project Name | `m365-governance-as-code` |
| Owner | `ph7x-Systems` |
| Repository name | `m365-governance-as-code` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

The GitHub side is an environment named exactly `pypi`, under Settings,
Environments. It exists so that publishing rights are not the same thing as
commit rights: anybody who can push can trigger CI, and only what this
environment allows can reach PyPI.

## Making a release

1. Bump `version` in `pyproject.toml` and add the CHANGELOG entry, through a
   pull request like anything else. `main` is protected.
2. Create a **GitHub Release** with the tag `v<version>`, targeting `main`.
   Mark it as a pre-release when the version is one.
3. Run `./tools/post-release-check.sh`. **Until it passes, the version is
   uploaded rather than released.**
4. The site follows in the same slice: install pins, the pages that describe
   changed behaviour, a page for any new contract. A published version with a
   manual describing the previous one is the documentation lying about the
   product.

**Create the release with its tag in one act.** A tag pushed on its own
triggers nothing, and leaves a tag with no release behind it. A tag can also be
moved, and a workflow that published on tag pushes would happily upload a
second artefact for a version that already exists.

## What the workflow checks before uploading

Both exist because a version number on PyPI is spent the moment it is used,
deleted or not.

- **The built version and the tag are the same string.** They drift the first
  time somebody tags and forgets to bump, and the result is a filename that
  disagrees with the release everybody is looking at.
- **`twine check --strict`**, which reads the metadata the way PyPI will.

## What cannot be fixed afterwards

**A release description is frozen at upload.** The description is the README,
rendered. If it contains a relative image path or a command that does not work,
correcting the file does not correct the published page: only another version
does.

That is not hypothetical. `1.0.0b1` shipped with `![...](docs/banner.png)`,
which GitHub resolves against the repository and PyPI cannot resolve at all, so
the project page opened with a broken image. **Every link and image in the
README must be an absolute URL.**

The same applies to the install command. While the only version is a
pre-release, `pip install m365-governance-as-code` resolves to nothing, because
pip skips pre-releases unless a version is pinned or `--pre` is given.

## After publishing, and the release is not done until this passes

```bash
./tools/post-release-check.sh <version>
```

**A successful upload proves the file arrived. It proves nothing about whether
anybody can install and run it.** `release-check.sh` proves the wheel this
repository builds; this proves the wheel a stranger downloads, which is a
different artefact reached by a different path.

The gate creates a throwaway environment, installs **from the public index**,
and refuses unless every one of these holds:

- the installed program reports the version that was released;
- `doctor` says the installation is sound;
- it evaluates packaged evidence and decides something;
- `list-rules`, `explain` and `validate` run;
- the contract bundle is in the wheel.

Then it destroys the environment. Nothing accumulates.

**`pip install` on its own is not the test, and on many machines it is not even
possible.** A modern Python refuses to install an application into the system
environment:

```text
error: externally-managed-environment
```

That is [PEP 668](https://peps.python.org/pep-0668/), enforced by Homebrew's
Python, Debian's and Ubuntu's. The README therefore gives `pipx`, which is the
recommended way to install a Python **application**, and this gate uses a
disposable virtual environment for the same reason.

Finally, open the project page and check the banner renders and the sidebar
links resolve, including the documentation link.

The first successful upload creates the project on PyPI, and the pending
publisher becomes an ordinary one on its own.
