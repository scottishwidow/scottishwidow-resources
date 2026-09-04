#!/usr/bin/env python3
"""File one GitHub issue per triaged finding.

The second half of ``design.md - Decision 4``: code scanning holds per-finding
state, Issues hold the work. Every *triaged* finding is promoted to an issue
carrying its key, verdict and rationale, whatever the verdict — deciding that a
finding is not worth acting on is the judgment this pipeline exists to inform,
and burying it in a dismissal comment hides it from where work is reviewed.

Three properties this module exists to hold, each of them a boundary rather
than a convenience:

- **It files under ``needs-triage`` and never under ``ready-for-agent``.** That
  label authorises unattended remediation, so an agent able to apply it would be
  authorising its own downstream work. The emittable vocabulary is a constant
  here and a label outside it raises rather than being filed.
- **It reads alert state and writes none of it.** The only reason this file
  speaks to the code scanning API at all is to resolve, per finding, the
  number of the alert it was filed for (``CONTEXT.md`` — Tracker item), so the
  two can be rejoined later without re-deriving a line number that has since
  moved. A ``not-applicable`` verdict still files an issue and still leaves the
  alert open; closing one is earned per rule under Decision 6 and happens
  elsewhere when it does.
- **It files only for findings the pipeline submitted for triage.** A verdict
  arriving for a vendored or below-threshold finding is reported as an error,
  not filed: the severity gate exists to keep those out, and quietly honouring
  such a verdict would defeat it.

Idempotency is keyed on the finding key, read back out of the bodies of existing
issues by ``issue_body.py``. A second run over unchanged verdicts creates
nothing and, in particular, edits no labels — a human disposition applied to an
issue is the output of this pipeline and must survive the next run of it.

Usage::

    file_issues.py --verdicts runs/<id>.json --findings normalised.json
    file_issues.py --verdicts run.json --findings f.json --dry-run
    file_issues.py --verdicts run.json --findings f.json --issues issues.json
    file_issues.py --verdicts run.json --findings f.json --alerts alerts.json
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

# The labels it may emit at all. `ready-for-agent` is absent by construction and
# a test asserts it: this is the boundary the remediation successor change
# depends on (`spec.md - Scenario: Agent judges a finding ready for unattended
# work`).
EMITTABLE_LABELS = (NEEDS_TRIAGE,)

# Named so that the guard fails loudly rather than by omission if someone adds
# a label parameter and forgets what it must never carry.
FORBIDDEN_LABELS = ("ready-for-agent",)

# Where a verdict lands when its rationale did not survive `collect_verdicts.py`.
UNDETERMINED = "undetermined"


class ForbiddenLabel(Exception):
    """A label outside the emittable vocabulary was about to be applied."""


def check_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    """Refuse to file under anything outside the emittable vocabulary."""
    for label in labels:
        if label in FORBIDDEN_LABELS or label not in EMITTABLE_LABELS:
            raise ForbiddenLabel(
                f"{label!r} is not a label this system may apply; "
                f"it may apply only: {', '.join(EMITTABLE_LABELS)}"
            )
    return labels


def gh_json(args: list[str]) -> Any:
    """Run a `gh` command that prints JSON, or fail loudly."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_issues() -> list[dict[str, Any]]:
    """Every issue, open or closed: a closed one still claims its key."""
    return gh_json(
        ["gh", "issue", "list", "--state", "all", "--limit", "500", "--json", "number,body"]
    )


def fetch_alerts() -> list[dict[str, Any]]:
    """Every open code scanning alert, for resolving a finding's alert number.

    Reading alert state is what widens this job to `security-events: read`
    (`CONTEXT.md` — Tracker item). Nothing here writes it back.

    Scoped to open alerts. A finding submitted for triage came from the current
    scan, so its alert is open; a fixed or dismissed alert at the same rule and
    location is a *former* state of that code and can only make the match below
    ambiguous.
    """
    return gh_json(
        ["gh", "api", "/repos/{owner}/{repo}/code-scanning/alerts?state=open", "--paginate"]
    )


def find_alert(finding: dict[str, Any], alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The code scanning alert this finding surfaced as, or ``None``.

    An alert is identified by rule plus *location* (`CONTEXT.md`), not by the
    finding key — the key exists so a *human reading an issue* need not match
    on a line number, but the alert itself carries no finding key, so matching
    on rule and declared location is the join available here.

    That match is not always unique. The finding key separates two
    instantiations of one module by module address; two alerts raised from the
    same line of that module do not differ in rule or location at all. An
    ambiguous match therefore resolves to ``None``: an issue with no alert row
    is one a human can still rejoin by hand, and an issue naming the wrong
    alert is a wrong answer nothing downstream can detect.
    """
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
    """The offending HCL, as the scanner reported it."""
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
    """The rationale, or why there is none.

    A record whose verdict was discarded reaches here with an empty rationale by
    design (`tasks.md` 4.5). The issue still says what happened, because the
    finding is exactly as outstanding as one nobody looked at, and a blank
    section would not say so.
    """
    if record.get("discarded_because"):
        discarded = record.get("discarded_verdict")
        proposed = f"`{discarded}`" if discarded else "a verdict"
        return (
            f"*No usable rationale was produced.* {proposed} was discarded because "
            f"{record['discarded_because']}, so this finding is recorded as "
            f"`{UNDETERMINED}` and needs a human judgment.\n"
        )
    return (record.get("rationale") or "").strip() + "\n"


def evidence_section(record: dict[str, Any]) -> str:
    """The cited paths, each marked if the corpus did not contain it.

    `evidence_discrepancy` is a subset of `evidence`, so a discrepant path is
    marked where it already stands rather than listed a second time below. A
    reader sees one list, and no path in it is unmarked and suspect at once.
    """
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
    """The **Alert** row's value: a link to the alert, never a bare ``#n``.

    A bare ``#42`` in an issue body is an *issue* autolink: GitHub renders it
    as a link to issue 42 and posts a cross-reference on it. The row exists so
    a human can reach the alert, so it is written as a link to the alert
    itself, and as a code span when no URL came back — either way, nothing
    that autolinks to an unrelated issue.
    """
    number = alert.get("number")
    url = alert.get("html_url") or ""
    return f"[#{number}]({url})" if url else f"`#{number}`"


def body(finding: dict[str, Any], record: dict[str, Any], alert: dict[str, Any] | None) -> str:
    """The issue body, in the shape `issue_body.py` reads back.

    The table's **Key** row is the join: this module's own idempotency finds a
    finding's issue by it, and nothing else in the body is load-bearing for
    that. **Alert** sits beside it, carrying the second identity — the code
    scanning alert this finding was filed for — so the two can be rejoined
    without re-deriving a line number that has since moved (`CONTEXT.md` —
    Tracker item). It is written only when a matching alert was resolved
    unambiguously; a body with none simply carries no such row. `alert` is
    required rather than defaulted: an issue filed without the row can never be
    rejoined, so omitting it is a decision to state, not one to fall into.
    """
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
    """Decide what to file, without filing anything.

    Split out from the filing so that every rule above is testable without a
    network, and so a `--dry-run` exercises the same decisions a real run makes.

    `alerts` has no default. An issue filed without its alert row can never be
    rejoined, so a caller that has no alerts to offer says so with an empty
    list rather than by omission.
    """
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

    for record in verdicts:
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

    triaged = {record.get("key") for record in verdicts}
    return {
        "create": create,
        "skipped_existing": skipped,
        "ineligible_verdicts": rejected,
        "untriaged_eligible": sorted(key for key in eligible if key not in triaged),
        # Stated rather than implied: no eligible finding was left out by a
        # filter, and nothing outside the eligible set was ever a candidate.
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
    for key in report["untriaged_eligible"]:
        print(f"warning: eligible finding carries no verdict, no issue filed: {key}", file=sys.stderr)
    for item in report["create"]:
        # An issue filed without this row can never be rejoined to its alert,
        # so a miss is said out loud rather than left to be noticed later.
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
        "untriaged_eligible": report["untriaged_eligible"],
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
