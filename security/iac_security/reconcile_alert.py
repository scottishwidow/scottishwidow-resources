#!/usr/bin/env python3
"""Dismiss the alert of a tracker item a human closed `wontfix`.

Deterministic and runs no model. It is the one thing here that writes alert
state, and it carries a human's decision rather than forming one.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from typing import Any, Protocol

import issue_body

# The label that says a finding will not be actioned (`docs/agents/triage-labels.md`).
# Reconciliation is keyed on it, not on the close: a merged remediation pull request
# closes its issue through `Fixes #N` with the remediation label still attached, and
# that alert must close on its own at the next scan rather than be dismissed here.
WONTFIX = "wontfix"

# GitHub's own `dismissed_reason` vocabulary, not this repository's.
WONT_FIX = "won't fix"

# What GitHub records for an issue closed as done, including by a `Fixes #N` merge.
COMPLETED = "completed"


class AlertClient(Protocol):
    def dismiss(self, alert: int, reason: str, comment: str) -> None: ...


class GitHubAlerts:
    """The code scanning API through `gh`, so the workflow's own token is the only credential."""

    def dismiss(self, alert: int, reason: str, comment: str) -> None:
        result = subprocess.run(
            [
                "gh", "api", "--method", "PATCH",
                f"/repos/{{owner}}/{{repo}}/code-scanning/alerts/{alert}",
                "-f", "state=dismissed",
                "-f", f"dismissed_reason={reason}",
                "-f", f"dismissed_comment={comment}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SystemExit(f"dismissing alert #{alert} failed: {result.stderr.strip()}")


def labels(item: dict[str, Any]) -> set[str]:
    """A webhook renders a label as an object and `gh issue list` as a string; both read back here."""
    return {
        entry.get("name", "") if isinstance(entry, dict) else str(entry)
        for entry in item.get("labels") or []
    }


def stands_at(item: dict[str, Any], dismiss: bool, reason: str, alert: int | None = None) -> dict[str, Any]:
    return {
        "issue": item.get("number"),
        "url": item.get("html_url") or "",
        "alert": alert,
        "dismiss": dismiss,
        "reason": reason,
    }


def decision(item: dict[str, Any]) -> dict[str, Any]:
    """Whether this closure dismisses an alert, and why it does or does not."""
    number = item.get("number")
    if WONTFIX not in labels(item):
        return stands_at(item, False, f"issue #{number} does not carry `{WONTFIX}`")
    if (item.get("state_reason") or "") == COMPLETED:
        return stands_at(
            item,
            False,
            f"issue #{number} was closed as completed, which says the finding is gone "
            f"rather than that it will not be actioned",
        )
    parsed = issue_body.parse(item.get("body") or "")
    if not parsed or parsed["alert"] is None:
        return stands_at(item, False, f"issue #{number} names no alert, so there is none to dismiss")
    return stands_at(
        item,
        True,
        f"issue #{number} was closed `{WONTFIX}`",
        parsed["alert"],
    )


def reconcile(item: dict[str, Any], client: AlertClient | None, dry_run: bool = False) -> dict[str, Any]:
    """Take the decision and, unless this is a dry run, carry it out."""
    taken = decision(item)
    taken["dry_run"] = dry_run
    if not taken["dismiss"] or dry_run:
        return taken
    if client is None:
        raise SystemExit("error: no alert client to dismiss with")
    client.dismiss(taken["alert"], WONT_FIX, taken["url"])
    return taken


def load(path: str) -> dict[str, Any]:
    snapshot = pathlib.Path(path)
    if not snapshot.is_file():
        raise SystemExit(f"error: no such issue snapshot: {path}")
    return json.loads(snapshot.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None, client: AlertClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--issue", required=True, help="the closed issue as JSON")
    parser.add_argument("--dry-run", action="store_true", help="decide everything and dismiss nothing")
    parser.add_argument("-o", "--output", help="write the report here instead of stdout")
    args = parser.parse_args(argv)

    item = load(args.issue)
    taken = reconcile(item, client or GitHubAlerts(), args.dry_run)

    if taken["dismiss"]:
        verb = "would dismiss" if args.dry_run else "dismissed"
        print(f"{verb} alert #{taken['alert']} as `{WONT_FIX}`: {taken['reason']}")
    else:
        print(f"nothing dismissed: {taken['reason']}")

    rendered = json.dumps(taken, indent=2) + "\n"
    if args.output:
        pathlib.Path(args.output).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
