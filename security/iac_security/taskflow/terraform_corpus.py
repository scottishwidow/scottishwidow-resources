#!/usr/bin/env python3
"""Assemble the repository's first-party Terraform as triage input.

ADR-0008 replaces `context.py`'s decision records with the **Terraform
corpus**: every first-party `.tf` file in this repository, pushed into every
finding's prompt as task id `corpus`. The framework ships no filesystem
toolbox, so the corpus is not fetched by the agent: it is read here and
rendered into the prompt, exactly as `context.py` did for ADRs. A run stays
reproducible from its inputs, and the exact bytes the model saw are
recoverable from the run manifest.

This is structurally the same shape as the module it replaces -- a
deterministic task that gathers files and pushes them into every prompt. The
distinction ADR-0008 draws is not the mechanism but what it may hold: this
module globs only `.tf` and never reads prose. A future reader who widens the
glob to "just the ADRs" has reversed that decision without touching it.

An empty corpus is an error, not an empty result. The prompt tells the agent
the corpus is complete and exhaustive, and the personality closes the "I was
not shown enough" escape on that promise. A missing root or a corpus of no
files means the promise is false, so this exits non-zero and `must_complete:
true` on the `corpus` task halts the run -- rather than triaging every finding
against nothing while claiming to have shown everything.

Usage::

    terraform_corpus.py                      # the corpus, as JSON
"""

from __future__ import annotations

import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]

# The two roots this repository maintains, matching `normalise.py`'s
# `FIRST_PARTY_PREFIXES`. Directories rather than a file list, so a new module
# or environment joins the corpus by existing.
CORPUS_DIRS = ("live", "modules")

# A resolved module cache can land inside either root once `terraform init` has
# run; it belongs to whoever publishes the module, not to this repository, and
# must stay out of the corpus exactly as it stays out of triage in
# `normalise.py`.
VENDORED_DIR_NAME = ".terraform"


def collect(root: pathlib.Path = REPO_ROOT) -> dict[str, object]:
    """Read every first-party `.tf` file, path-sorted, as one JSON object."""
    documents: list[dict[str, str]] = []
    missing: list[str] = []

    for relative in CORPUS_DIRS:
        directory = root / relative
        if not directory.is_dir():
            missing.append(relative)
            continue
        for path in directory.rglob("*.tf"):
            if VENDORED_DIR_NAME in path.relative_to(root).parts:
                continue
            documents.append(
                {
                    "path": str(path.relative_to(root)),
                    "text": path.read_text(encoding="utf-8"),
                }
            )

    documents.sort(key=lambda document: document["path"])

    return {
        "documents": documents,
        "missing_dirs": missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    # The global rather than `collect`'s default, which is bound once at import
    # and so cannot be pointed at a fabricated tree by a test.
    collected = collect(REPO_ROOT)

    if collected["missing_dirs"]:
        raise SystemExit(
            "error: no such corpus directory: "
            + ", ".join(collected["missing_dirs"])
            + f" (looked under {REPO_ROOT})"
        )

    if not collected["documents"]:
        raise SystemExit(
            f"error: the Terraform corpus is empty (looked under {REPO_ROOT}); "
            "the prompt promises the agent a complete corpus, so an empty one "
            "is a broken run rather than a run with nothing to say"
        )

    rendered = json.dumps(collected, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
