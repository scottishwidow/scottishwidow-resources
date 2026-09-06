#!/usr/bin/env python3
"""The unified diff a remediation run produced, taken out of its manifest.

The remediator holds no tools, so the patch arrives as response text and every
write of it is done outside the agent -- here, and by the workflow that carries
it to the patch gate.
"""

from __future__ import annotations

import argparse
import json
import pathlib

import collect_verdicts

PATCH_TASK = "patch"

# What `patch_gate.touched_files` parses, so a reply that is prose rather than a
# diff is caught here instead of failing a gate that has nothing to read.
FILE_HEADER_PREFIX = "diff --git "


def patch_of(manifest: dict[str, object], output_id: str = PATCH_TASK) -> str:
    """The diff text, unfenced; a manifest that carries no patch raises rather than writing an empty file."""
    outputs = manifest.get("outputs") or {}
    if output_id not in outputs:
        raise SystemExit(
            f"manifest has no output {output_id!r}; it has: "
            + (", ".join(sorted(outputs)) or "(none)")
        )
    produced = outputs[output_id]
    if not isinstance(produced, str) or not produced.strip():
        raise SystemExit(f"output {output_id!r} carries no text; the remediator produced no patch")

    diff = collect_verdicts.unfence(produced).strip() + "\n"
    if FILE_HEADER_PREFIX not in diff:
        raise SystemExit(
            f"the remediator produced no patch: a unified diff starts a file section with "
            f"`{FILE_HEADER_PREFIX}` and this reply has none. It reads:\n" + diff
        )
    return diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", help="path to a run manifest.json")
    source.add_argument(
        "--latest", action="store_true", help=f"use the newest manifest under {collect_verdicts.RUNS}"
    )
    parser.add_argument("--output-id", default=PATCH_TASK, help="the taskflow task id to read")
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    path = (
        collect_verdicts.latest_manifest() if args.latest else pathlib.Path(args.manifest)
    )
    diff = patch_of(json.loads(path.read_text(encoding="utf-8")), args.output_id)

    if args.output:
        out = pathlib.Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(diff, encoding="utf-8")
    else:
        print(diff, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
