#!/usr/bin/env python3
"""Collect the repository's decision records as triage context.

`design.md - Decision 7` makes ADRs and design documents agent input. The
framework ships no filesystem toolbox, so context is not fetched by the agent:
it is read here and rendered into the prompt. That is the stricter arrangement
and the one worth having. A run is reproducible from its inputs, the exact
bytes the model saw are recoverable from the run manifest, and the agent cannot
wander into alert state and read a verdict it is about to be scored against.

The cost is the token bill -- every document goes into every finding's prompt --
which is affordable only because the two deterministic filters cut the corpus to
seven. It would not be at twenty.

`--without-context` yields the empty document set, which is the "without" arm of
the comparison deferred in `tasks.md` 5.2. It is wired here rather than left for
later so that the arm costs a flag rather than a rewrite.

Usage::

    context.py                      # ADRs and design docs, as JSON
    context.py --without-context    # the empty set, same shape
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]

# Ordered, and directories rather than a file list, so a new ADR becomes triage
# context by existing. Nothing here needs updating when one is added.
CONTEXT_DIRS = ("docs/adr", "docs/design")


def collect(root: pathlib.Path = REPO_ROOT, include: bool = True) -> dict[str, object]:
    """Read the context documents, newest-numbered last, as one JSON object."""
    documents: list[dict[str, str]] = []
    missing: list[str] = []

    if include:
        for relative in CONTEXT_DIRS:
            directory = root / relative
            if not directory.is_dir():
                missing.append(relative)
                continue
            for path in sorted(directory.glob("*.md")):
                documents.append(
                    {
                        "path": str(path.relative_to(root)),
                        "text": path.read_text(encoding="utf-8"),
                    }
                )

    return {
        "documents": documents,
        "included": include,
        "missing_dirs": missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--without-context",
        action="store_true",
        help="emit no documents (the control arm of the context comparison)",
    )
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    collected = collect(include=not args.without_context)

    if collected["missing_dirs"]:
        print(
            "warning: no such context directory: "
            + ", ".join(collected["missing_dirs"]),
            file=sys.stderr,
        )

    rendered = json.dumps(collected, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
