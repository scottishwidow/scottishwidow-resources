#!/usr/bin/env python3
"""Export the ground-truth fixture from recorded triage decisions.

Verdicts are recorded where the triage happens — as a dismissal comment on a code
scanning alert, or on the issue an open alert was promoted to — and this tool
snapshots them into ``fixtures/ground-truth.yaml``. It is an export, never an
authoring step: nothing here forms a verdict, and a finding nobody has triaged is
reported as outstanding rather than given one (``design.md - Decision 5``).

The fixture covers exactly the findings the system submits for triage. A vendored
or below-threshold finding carrying a verdict is an error, not an extra entry:
scoring the agent on findings it was never shown is the mistake the severity gate
exists to prevent.

Each entry carries ``verdict_author``. A fixture is only as good as the
independence of the verdicts in it, and a verdict written by a model cannot score
that same model — so provenance travels with the verdict rather than being
remembered out of band. An entry that never declared its provenance is exported
as ``unknown`` and the scorer refuses to count it.

Usage::

    export_fixture.py                       # live: reads gh, writes the fixture
    export_fixture.py --alerts a.json --issues i.json --report scan.json -o out.yaml
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys
from typing import Any

import yaml

import issue_body
import normalise

HERE = pathlib.Path(__file__).resolve().parent
BASELINE = HERE / "fixtures" / "baseline-scan.json"
FIXTURE = HERE / "fixtures" / "ground-truth.yaml"

# Triage runs write here. The fixture must predate the first one, so its
# existence is the signal that the ordering constraint has already been spent.
TRIAGE_RUNS = HERE / "runs"

# A dismissal is the recorded form of "this does not apply here"; the vocabulary
# has one verdict for that, and the dismissal comment carries its rationale.
DISMISSAL_VERDICT = "not-applicable"

ALERTS_ENDPOINT = "/repos/:owner/:repo/code-scanning/alerts"


def gh_json(args: list[str]) -> Any:
    """Run a `gh` command that prints JSON, or fail loudly."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_alerts() -> list[dict[str, Any]]:
    return gh_json(["gh", "api", ALERTS_ENDPOINT, "--paginate"])


def fetch_issues() -> list[dict[str, Any]]:
    return gh_json(
        ["gh", "issue", "list", "--state", "all", "--limit", "500", "--json", "number,body"]
    )


def alert_join_key(rule_id: str, path: str, start_line: Any) -> tuple[str, str, Any]:
    """What identifies an alert to a normalised record.

    Not the finding key: an alert does not carry one. Rule, path and line are
    unique across every first-party finding in this corpus — the only collisions
    are the four vendored `AWS-0104` pairs (`design.md - Decision 3`) — and this
    join is only ever asked about findings that reached triage.
    """
    return (rule_id, path, start_line)


def index_alerts(alerts: list[dict[str, Any]]) -> dict[tuple, list[dict[str, Any]]]:
    index: dict[tuple, list[dict[str, Any]]] = {}
    for alert in alerts:
        location = alert.get("most_recent_instance", {}).get("location", {})
        join = alert_join_key(
            alert.get("rule", {}).get("id", ""),
            location.get("path", ""),
            location.get("start_line"),
        )
        index.setdefault(join, []).append(alert)
    return index


def index_issues(issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Parsed issue verdicts, keyed by the finding key in the issue body."""
    index: dict[str, dict[str, Any]] = {}
    for issue in issues:
        parsed = issue_body.parse(issue.get("body") or "")
        if parsed is None:
            continue
        parsed["issue"] = issue.get("number")
        index.setdefault(parsed["key"], parsed)
    return index


def alert_for(record: dict[str, Any], index: dict[tuple, list[dict[str, Any]]]) -> dict | None:
    """The single alert a record joins to, or ``None`` if that is ambiguous."""
    join = alert_join_key(record["rule_id"], record["code_path"], record["start_line"])
    matches = index.get(join, [])
    return matches[0] if len(matches) == 1 else None


def verdict_from_dismissal(alert: dict[str, Any]) -> dict[str, Any]:
    """A dismissed alert carries its verdict in the act and its reason in the comment."""
    comment = alert.get("dismissed_comment") or ""
    return {
        "verdict": DISMISSAL_VERDICT,
        # Dismissing an alert is an act only a person with write access can
        # perform, so a dismissal is human unless something later proves otherwise.
        "verdict_author": issue_body.HUMAN,
        "rationale": comment.strip(),
        "evidence": issue_body.parse_evidence(comment),
        "recorded_on": "alert",
    }


def verdict_from_issue(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": parsed["verdict"],
        "verdict_author": parsed["verdict_author"],
        "rationale": parsed["rationale"],
        "evidence": parsed["evidence"],
        "recorded_on": "issue",
        "issue": parsed["issue"],
    }


def build(
    normalised: dict[str, Any],
    alerts: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    """Join recorded verdicts onto the eligible findings."""
    alert_index = index_alerts(alerts)
    issue_index = index_issues(issues)

    entries: list[dict[str, Any]] = []
    untriaged: list[str] = []
    unjoined: list[str] = []

    for record in normalised["eligible"]:
        key = record["key"]
        alert = alert_for(record, alert_index)
        if alert is None:
            unjoined.append(key)

        recorded = issue_index.get(key)
        if recorded and recorded["verdict"]:
            entry = verdict_from_issue(recorded)
        elif alert is not None and alert.get("state") == "dismissed":
            entry = verdict_from_dismissal(alert)
        else:
            untriaged.append(key)
            continue

        entry.update(
            {
                "key": key,
                "rule_id": record["rule_id"],
                "severity": record["severity"],
                "alert": alert.get("number") if alert else None,
                "alert_state": alert.get("state") if alert else None,
            }
        )
        entries.append(
            {
                k: entry[k]
                for k in (
                    "key",
                    "rule_id",
                    "severity",
                    "verdict",
                    "verdict_author",
                    "rationale",
                    "evidence",
                    "recorded_on",
                    "issue",
                    "alert",
                    "alert_state",
                )
                if k in entry
            }
        )

    ineligible = ineligible_verdicts(normalised, alert_index, issue_index)

    return {
        "severity_threshold": normalised["severity_threshold"],
        "exported_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "eligible_findings": len(normalised["eligible"]),
        "untriaged_keys": sorted(untriaged),
        "unjoined_keys": sorted(unjoined),
        "ineligible_verdicts": ineligible,
        "entries": sorted(entries, key=lambda e: e["key"]),
    }


def ineligible_verdicts(
    normalised: dict[str, Any],
    alert_index: dict[tuple, list[dict[str, Any]]],
    issue_index: dict[str, dict[str, Any]],
) -> list[str]:
    """Findings that were triaged despite never being submitted for triage.

    A verdict here is a corpus the scorer can never legitimately use, so it is
    reported rather than exported (`spec.md - Triage accuracy is measured against
    a fixed corpus`).
    """
    offenders: list[str] = []
    for record in normalised["below_threshold"] + normalised["vendored"]:
        if record["key"] in issue_index and issue_index[record["key"]]["verdict"]:
            offenders.append(record["key"])
            continue
        alert = alert_for(record, alert_index)
        if alert is not None and alert.get("state") == "dismissed":
            offenders.append(record["key"])
    return sorted(set(offenders))


def block_scalars(dumper: yaml.SafeDumper, value: str):
    """Render multi-line rationales as literal blocks, so they stay readable."""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


class FixtureDumper(yaml.SafeDumper):
    pass


FixtureDumper.add_representer(str, block_scalars)


def render(fixture: dict[str, Any]) -> str:
    header = (
        "# Ground-truth verdicts for the triage-eligible findings.\n"
        "#\n"
        "# Exported from recorded triage decisions by export_fixture.py; do not edit by\n"
        "# hand. Re-run the export instead, so the fixture stays a snapshot of alert and\n"
        "# issue state rather than a second place a verdict is authored.\n"
        "#\n"
        "# `verdict_author` is load-bearing: only `human` entries may contribute to an\n"
        "# agreement figure. See design.md - Decision 5.\n"
    )
    return header + yaml.dump(
        fixture,
        Dumper=FixtureDumper,
        sort_keys=False,
        default_flow_style=False,
        width=88,
        # Without this every em dash escapes and the literal block collapses into
        # a quoted one-liner, which is exactly the readability the fixture needs.
        allow_unicode=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", default=str(BASELINE), help="Trivy config JSON report")
    parser.add_argument("--alerts", help="alert JSON; fetched with gh when omitted")
    parser.add_argument("--issues", help="issue JSON; fetched with gh when omitted")
    parser.add_argument("-o", "--output", default=str(FIXTURE))
    parser.add_argument(
        "--allow-after-triage",
        action="store_true",
        help="export even though a triage run already exists (the result is not ground truth)",
    )
    args = parser.parse_args(argv)

    if TRIAGE_RUNS.exists() and any(TRIAGE_RUNS.iterdir()) and not args.allow_after_triage:
        raise SystemExit(
            f"refusing to export: {TRIAGE_RUNS} exists, so a triage run may already have "
            "happened and these verdicts cannot be treated as independent ground truth "
            "(design.md - Decision 5). Pass --allow-after-triage to override."
        )

    with open(args.report, encoding="utf-8") as handle:
        normalised = normalise.normalise(json.load(handle))

    alerts = json.load(open(args.alerts, encoding="utf-8")) if args.alerts else fetch_alerts()
    issues = json.load(open(args.issues, encoding="utf-8")) if args.issues else fetch_issues()

    fixture = build(normalised, alerts, issues)

    for key in fixture["untriaged_keys"]:
        print(f"outstanding: no recorded verdict for {key}", file=sys.stderr)
    for key in fixture["unjoined_keys"]:
        print(f"warning: no unambiguous alert for {key}", file=sys.stderr)
    for key in fixture["ineligible_verdicts"]:
        print(f"error: verdict recorded against an ineligible finding: {key}", file=sys.stderr)
    for entry in fixture["entries"]:
        if entry["verdict_author"] != issue_body.HUMAN:
            print(
                f"warning: {entry['key']} carries a {entry['verdict_author']} verdict and "
                "cannot contribute to an agreement figure",
                file=sys.stderr,
            )

    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(render(fixture))
    print(
        f"exported {len(fixture['entries'])} of {fixture['eligible_findings']} "
        f"eligible findings to {args.output}",
        file=sys.stderr,
    )
    return 1 if fixture["ineligible_verdicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
