#!/usr/bin/env python3
"""The eligible findings this run must actually triage.

Triage costs nothing when nothing changed: a finding that already carries a
tracker item is dropped here, before the fan-out reaches a model. The rule is a
property of the tracker rather than of the finding, so it lives here and not in
`normalise.py`, which stays pure and makes no network call.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
TRIAGE_DIR = HERE.parent

sys.path.insert(0, str(TRIAGE_DIR))
import issue_body  # noqa: E402

TRACKER_FIELDS = "number,state,body,comments"

BYPASS_VALUES = ("1", "true", "yes", "on")


def fetch_tracker() -> list[dict[str, Any]]:
    """Read the tracker with `gh`, when no snapshot was handed to this run."""
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "all", "--limit", "500", "--json", TRACKER_FIELDS],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "error: could not read the tracker: " + (result.stderr.strip() or "gh failed")
        )
    return json.loads(result.stdout)


def load_tracker(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return fetch_tracker()
    snapshot = pathlib.Path(path)
    if not snapshot.is_file():
        raise SystemExit(f"error: no such tracker snapshot: {path}")
    return json.loads(snapshot.read_text(encoding="utf-8"))


def select(
    findings: dict[str, Any], issues: list[dict[str, Any]], bypass: bool = False
) -> dict[str, Any]:
    """Partition the eligible set into what this run triages and what the tracker already holds."""
    eligible = findings.get("eligible", [])
    if bypass:
        return {"findings": eligible, "excluded": [], "retriaged": [], "bypassed": True}

    items = issue_body.tracker_items(issues)

    outstanding: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    retriaged: list[str] = []

    for record in eligible:
        item = items.get(record["key"])
        if item is None:
            outstanding.append(record)
            continue
        if issue_body.awaits_a_verdict(item):
            outstanding.append(record)
            retriaged.append(record["key"])
            continue
        excluded.append({"key": record["key"], **item})

    return {
        "findings": outstanding,
        "excluded": excluded,
        "retriaged": retriaged,
        "bypassed": False,
    }


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in BYPASS_VALUES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("findings", nargs="?", help="normalised findings JSON; stdin when omitted")
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    source = open(args.findings, encoding="utf-8") if args.findings else sys.stdin
    with source:
        findings = json.load(source)

    bypass = env_flag("TRIAGE_BYPASS_TRACKER")
    selected = select(findings, [] if bypass else load_tracker(os.environ.get("TRACKER_ITEMS")), bypass)

    if selected["bypassed"]:
        print(
            "the tracker was bypassed: every eligible finding is triaged again",
            file=sys.stderr,
        )
    for entry in selected["excluded"]:
        print(
            f"already tracked as #{entry['issue']} ({entry['state'].lower()}, "
            f"{entry['verdict'] or 'no verdict recorded'}), not triaged: {entry['key']}",
            file=sys.stderr,
        )
    for key in selected["retriaged"]:
        print(f"tracker item still awaits a verdict, triaged again: {key}", file=sys.stderr)

    rendered = json.dumps(selected, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
