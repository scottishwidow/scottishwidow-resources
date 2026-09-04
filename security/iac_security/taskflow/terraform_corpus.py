#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]

# Matches `normalise.py`'s `FIRST_PARTY_PREFIXES`.
CORPUS_DIRS = ("live", "modules")

# A resolved module cache belongs to whoever publishes the module, not this repository.
VENDORED_DIR_NAME = ".terraform"


def collect(root: pathlib.Path = REPO_ROOT) -> dict[str, object]:
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
    parser = argparse.ArgumentParser(
        description="Assemble the repository's first-party Terraform as triage input."
    )
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    # Passed explicitly rather than relying on `collect`'s default, so a test can point it elsewhere.
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
