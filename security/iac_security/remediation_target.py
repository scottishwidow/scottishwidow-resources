#!/usr/bin/env python3
"""What the remediator is shown: one finding, its tracker item, and the paths a patch may touch.

Deterministic and tokenless. Remediation is invoked by a label, so the first
thing asked of a labelled issue is whether it holds a finding key at all: one
that does not stops the run here, before anything costs money.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import posixpath
import sys
from typing import Any

import issue_body
import vocabulary

# The issue as `gh issue view --json number,body,comments` renders it, read on
# the host where a token is; the body alone when there is nothing to read it with.
ITEM_ENV = "ISSUE_ITEM"
BODY_ENV = "ISSUE_BODY"


def load_item(path: str | None) -> dict[str, Any]:
    if not path:
        return {"body": os.environ.get(BODY_ENV, "")}
    snapshot = pathlib.Path(path)
    if not snapshot.is_file():
        raise SystemExit(f"error: no such issue snapshot: {path}")
    return json.loads(snapshot.read_text(encoding="utf-8"))


def comments_of(item: dict[str, Any]) -> list[str]:
    return [entry.get("body") or "" for entry in item.get("comments") or []]


def tracker_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """The triager's record as the issue now stands, or `None` if it holds no finding key."""
    body = item.get("body") or ""
    parsed = issue_body.parse(body)
    if not parsed:
        return None

    comments = comments_of(item)
    standing = issue_body.standing_verdict(body, comments)
    recorded = issue_body.known_verdict(standing)
    return {
        "number": item.get("number"),
        "key": parsed["key"],
        "alert": parsed["alert"],
        # An unanswered template prompt reads back as no verdict at all, and a
        # finding awaiting one is `undetermined` rather than whatever the label
        # implies: the label authorises a patch, it does not judge the finding.
        "verdict": standing if recorded else vocabulary.UNDETERMINED,
        "verdict_recorded": recorded,
        "rationale": parsed["rationale"],
        "body": body,
        "comments": comments,
    }


def permitted_paths(finding: dict[str, Any]) -> dict[str, Any]:
    """The paths `patch_gate.path_is_permitted` accepts, named for the prompt rather than re-decided."""
    return {
        "editable": sorted({finding["code_path"], finding["owner_path"]}),
        "new_files_under": posixpath.dirname(finding["code_path"]),
    }


def eligible_matches(findings: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [record for record in findings.get("eligible", []) if record["key"] == key]


def target(findings: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """The remediator's whole input, assembled from the scan and the issue."""
    tracked = tracker_item(item)
    if tracked is None:
        raise SystemExit("error: the issue body carries no finding key; there is nothing to remediate")

    matched = eligible_matches(findings, tracked["key"])
    if not matched:
        raise SystemExit(
            f"error: {tracked['key']} is not an eligible finding in this scan; "
            "it may have been fixed, dropped below the threshold, or never been first-party"
        )
    if len(matched) > 1:
        raise SystemExit(
            f"error: {tracked['key']} names {len(matched)} eligible findings, so the key "
            "identifies no single one to patch"
        )

    finding = matched[0]
    return {
        "finding": finding,
        "issue": tracked,
        "permitted_paths": permitted_paths(finding),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("findings", nargs="?", help="normalised findings JSON; stdin when omitted")
    parser.add_argument("--issue", help=f"issue snapshot JSON; ${ITEM_ENV} when omitted")
    parser.add_argument(
        "--key-only",
        action="store_true",
        help="print the finding key the issue body carries, and nothing else",
    )
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    item = load_item(args.issue or os.environ.get(ITEM_ENV))

    if args.key_only:
        tracked = tracker_item(item)
        if tracked:
            print(tracked["key"])
        return 0

    source = open(args.findings, encoding="utf-8") if args.findings else sys.stdin
    with source:
        findings = json.load(source)

    assembled = target(findings, item)
    print(
        f"remediating {assembled['finding']['key']} "
        f"({assembled['issue']['verdict']}, issue #{assembled['issue']['number']})",
        file=sys.stderr,
    )

    rendered = json.dumps(assembled, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
