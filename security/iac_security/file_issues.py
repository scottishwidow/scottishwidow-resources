#!/usr/bin/env python3
"""File one GitHub issue per triaged finding.

See `docs/design/iac-security-triage.md` — Decisions that are load-bearing in the code.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

import issue_body

HERE = pathlib.Path(__file__).resolve().parent

# The one label this system may apply, from `docs/agents/triage-labels.md`.
NEEDS_TRIAGE = "needs-triage"

# `ready-for-agent` is absent by construction: it authorises unattended remediation.
EMITTABLE_LABELS = (NEEDS_TRIAGE,)

FORBIDDEN_LABELS = ("ready-for-agent",)

UNDETERMINED = "undetermined"

# The discard rule reaches a finding whose branch never produced a record at all.
DISCARDED_NO_RECORD = "the triage run produced no verdict record for it"


class ForbiddenLabel(Exception):
    pass


def check_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    for label in labels:
        if label in FORBIDDEN_LABELS or label not in EMITTABLE_LABELS:
            raise ForbiddenLabel(
                f"{label!r} is not a label this system may apply; "
                f"it may apply only: {', '.join(EMITTABLE_LABELS)}"
            )
    return labels


def gh_json(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_issues() -> list[dict[str, Any]]:
    """A closed issue still claims its key, so this reads all states."""
    return gh_json(
        ["gh", "issue", "list", "--state", "all", "--limit", "500", "--json", "number,body"]
    )


def fetch_alerts() -> list[dict[str, Any]]:
    """Open alerts only: a fixed or dismissed one is a former state that could only confuse the match below."""
    return gh_json(
        ["gh", "api", "/repos/{owner}/{repo}/code-scanning/alerts?state=open", "--paginate"]
    )


def find_alert(finding: dict[str, Any], alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Matched by rule plus location, since an alert carries no finding key; an ambiguous match is `None`."""
    rule_id = finding.get("rule_id")
    path = finding.get("code_path")
    start = finding.get("start_line")
    matched = []
    for alert in alerts:
        if (alert.get("rule") or {}).get("id") != rule_id:
            continue
        location = ((alert.get("most_recent_instance") or {}).get("location")) or {}
        if location.get("path") != path:
            continue
        if start is not None and location.get("start_line") != start:
            continue
        matched.append(alert)
    return matched[0] if len(matched) == 1 else None


def existing_keys(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Finding key -> issue number, for issues that carry a key."""
    found: dict[str, int] = {}
    for issue in issues:
        parsed = issue_body.parse(issue.get("body") or "")
        if parsed and parsed["key"] not in found:
            found[parsed["key"]] = issue.get("number")
    return found


def title(finding: dict[str, Any]) -> str:
    """`[RULE] What the rule is about — where it fired`."""
    where = f"{finding.get('module_address', '')}:{finding.get('resource_address', '')}"
    return f"[{finding['rule_id']}] {finding.get('title') or finding['rule_id']} — {where}"


def code_block(finding: dict[str, Any]) -> str:
    lines = finding.get("code") or []
    if not lines:
        return ""
    body = "\n".join(line.get("content", "") for line in lines)
    return f"```hcl\n{body}\n```\n\n"


def declared_at(finding: dict[str, Any]) -> str:
    start, end = finding.get("start_line"), finding.get("end_line")
    path = finding.get("code_path", "")
    if start is None:
        return f"`{path}`"
    return f"`{path}:{start}-{end}`" if end and end != start else f"`{path}:{start}`"


def rationale_section(record: dict[str, Any]) -> str:
    """A discarded verdict still says so, rather than leaving a blank section indistinguishable from unreviewed."""
    reason = record.get("discarded_because")
    if not reason:
        return (record.get("rationale") or "").strip() + "\n"
    discarded = record.get("discarded_verdict")
    opening = (
        f"`{discarded}` was discarded because {reason}"
        if discarded
        else f"No verdict stands, because {reason}"
    )
    return (
        f"*No usable rationale was produced.* {opening}, so this finding is "
        f"recorded as `{UNDETERMINED}` and needs a human judgment.\n"
    )


def record_without_a_verdict(key: str) -> dict[str, Any]:
    """The record an eligible finding is filed under when no verdict reached the filing step."""
    return {
        "key": key,
        "verdict": UNDETERMINED,
        "rationale": "",
        "evidence": [],
        "discarded_because": DISCARDED_NO_RECORD,
    }


def evidence_section(record: dict[str, Any]) -> str:
    """A discrepant path is marked where it already stands, not listed a second time."""
    evidence = record.get("evidence") or []
    if not evidence:
        return "*None.* No Terraform corpus file was cited for this finding.\n"

    unknown = set(record.get("evidence_discrepancy") or [])
    lines = [
        f"- `{path}`" + (" — **not in the Terraform corpus**" if path in unknown else "")
        for path in evidence
    ]
    if unknown:
        lines.append(
            "\nA marked path was cited but was not in the corpus this verdict was "
            "formed from, so the agent was never shown it. The verdict is recorded "
            "rather than discarded: the citation may be wrong while the judgment is "
            "right.\n"
        )
    return "\n".join(lines) + "\n"


def alert_cell(alert: dict[str, Any]) -> str:
    """Never a bare ``#42``: GitHub reads that as an autolink to issue 42, not the alert."""
    number = alert.get("number")
    url = alert.get("html_url") or ""
    return f"[#{number}]({url})" if url else f"`#{number}`"


def body(finding: dict[str, Any], record: dict[str, Any], alert: dict[str, Any] | None) -> str:
    """In the shape `issue_body.py` reads back. `alert` has no default: omitting the row is a decision to state."""
    rule_id = finding["rule_id"]
    url = finding.get("primary_url") or ""
    rule_cell = f"[{rule_id}]({url})" if url else f"`{rule_id}`"
    rule_title = finding.get("title") or ""

    rows = [("Key", f"`{record['key']}`")]
    if alert is not None:
        rows.append(("Alert", alert_cell(alert)))
    rows += [
        ("Rule", f"{rule_cell} — {rule_title}" if rule_title else rule_cell),
        ("Severity", finding.get("severity", "")),
        ("Instantiated at", f"`{finding.get('owner_path', '')}`"),
        ("Declared at", declared_at(finding)),
        ("Module", f"`{finding.get('module_address', '')}`"),
        ("Resource", f"`{finding.get('resource_address', '')}`"),
    ]
    table = "| | |\n|---|---|\n" + "".join(f"| **{name}** | {value} |\n" for name, value in rows)

    scanner = ""
    if finding.get("message"):
        scanner += f"**What the scanner says:** {finding['message']}\n\n"
    if finding.get("resolution"):
        scanner += f"**Suggested resolution:** {finding['resolution']}\n\n"

    return (
        "## Finding\n\n"
        f"{table}\n"
        f"{code_block(finding)}"
        f"{scanner}"
        f"## Verdict\n\n`{record['verdict']}`\n\n"
        f"## Rationale\n\n{rationale_section(record)}\n"
        f"## Evidence\n\n{evidence_section(record)}\n"
        "---\n\n"
        f"*Filed by the IaC triage pipeline under `{NEEDS_TRIAGE}`. The verdict above is a\n"
        "proposal, not a disposition: apply `ready-for-agent`, `ready-for-human` or\n"
        "`wontfix` from `docs/agents/triage-labels.md` to say what happens next. The\n"
        "pipeline never applies `ready-for-agent` itself\n"
        "(`docs/design/iac-security-triage.md` — Decisions that are load-bearing in the\n"
        "code), and it leaves this finding's code scanning alert open whatever the\n"
        "verdict says.*\n"
    )


def plan(
    findings: dict[str, Any],
    verdicts: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Decide what to file, without filing anything, so `--dry-run` exercises the same decisions a real run makes."""
    eligible = {record["key"]: record for record in findings.get("eligible", [])}
    ineligible = {
        record["key"]: status
        for status, group in (
            ("below-threshold", findings.get("below_threshold", [])),
            ("vendored", findings.get("vendored", [])),
        )
        for record in group
    }
    already = existing_keys(issues)

    create: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    triaged = {record.get("key") for record in verdicts}
    without_a_verdict = sorted(key for key in eligible if key not in triaged)

    for record in [*verdicts, *(record_without_a_verdict(key) for key in without_a_verdict)]:
        key = record.get("key") or ""
        if key not in eligible:
            rejected.append(
                {
                    "key": key,
                    "reason": ineligible.get(key, "not an eligible finding in this scan"),
                }
            )
            continue
        if key in already:
            skipped.append({"key": key, "issue": already[key]})
            continue
        finding = eligible[key]
        alert = find_alert(finding, alerts)
        create.append(
            {
                "key": key,
                "rule_id": finding["rule_id"],
                "verdict": record["verdict"],
                "alert": alert.get("number") if alert else None,
                "title": title(finding),
                "body": body(finding, record, alert),
                "labels": check_labels(EMITTABLE_LABELS),
            }
        )

    return {
        "create": create,
        "skipped_existing": skipped,
        "ineligible_verdicts": rejected,
        "filed_without_a_verdict": without_a_verdict,
        "not_filed_below_threshold": sorted(
            r["key"] for r in findings.get("below_threshold", [])
        ),
        "not_filed_vendored": sorted(r["key"] for r in findings.get("vendored", [])),
    }


def create_issue(item: dict[str, Any]) -> int:
    """File one issue and return its number."""
    check_labels(tuple(item["labels"]))
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as handle:
        handle.write(item["body"])
        body_file = handle.name
    try:
        args = ["gh", "issue", "create", "--title", item["title"], "--body-file", body_file]
        for label in item["labels"]:
            args += ["--label", label]
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"gh issue create failed: {result.stderr.strip()}")
        url = result.stdout.strip().splitlines()[-1]
    finally:
        pathlib.Path(body_file).unlink(missing_ok=True)
    return int(url.rstrip("/").rsplit("/", 1)[-1])


def load(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--findings", required=True, help="normalised findings JSON")
    parser.add_argument("--verdicts", required=True, help="verdict records from collect_verdicts.py")
    parser.add_argument("--issues", help="existing issues JSON; reads `gh` when omitted")
    parser.add_argument("--alerts", help="code scanning alerts JSON; reads `gh` when omitted")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="decide everything and file nothing",
    )
    parser.add_argument("-o", "--output", help="write the report here instead of stdout")
    args = parser.parse_args(argv)

    findings = load(args.findings)
    verdicts = load(args.verdicts)
    issues = load(args.issues) if args.issues else fetch_issues()
    alerts = load(args.alerts) if args.alerts else fetch_alerts()

    report = plan(findings, verdicts, issues, alerts)

    for item in report["ineligible_verdicts"]:
        print(
            f"error: verdict for a finding that was never submitted for triage "
            f"({item['reason']}): {item['key'] or '(unidentified)'}",
            file=sys.stderr,
        )
    for key in report["filed_without_a_verdict"]:
        print(
            f"warning: eligible finding carries no verdict, filed as {UNDETERMINED}: {key}",
            file=sys.stderr,
        )
    for item in report["create"]:
        if item["alert"] is None:
            print(
                f"warning: no single code scanning alert matches this finding, "
                f"issue filed with no alert row: {item['key']}",
                file=sys.stderr,
            )

    filed = []
    for item in report["create"]:
        if args.dry_run:
            filed.append(
                {
                    "key": item["key"],
                    "issue": None,
                    "verdict": item["verdict"],
                    "alert": item["alert"],
                }
            )
            continue
        number = create_issue(item)
        print(f"filed #{number} for {item['key']} ({item['verdict']})", file=sys.stderr)
        filed.append(
            {
                "key": item["key"],
                "issue": number,
                "verdict": item["verdict"],
                "alert": item["alert"],
            }
        )

    for item in report["skipped_existing"]:
        print(f"already filed as #{item['issue']}: {item['key']}", file=sys.stderr)

    summary = {
        "dry_run": args.dry_run,
        "filed": filed,
        "skipped_existing": report["skipped_existing"],
        "ineligible_verdicts": report["ineligible_verdicts"],
        "filed_without_a_verdict": report["filed_without_a_verdict"],
        "not_filed_below_threshold": report["not_filed_below_threshold"],
        "not_filed_vendored": report["not_filed_vendored"],
    }
    rendered = json.dumps(summary, indent=2) + "\n"
    if args.output:
        out = pathlib.Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    return 1 if report["ineligible_verdicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
