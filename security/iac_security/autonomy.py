#!/usr/bin/env python3
"""Decide which alerts the system may dismiss without a human, and dismiss them.

The ratchet of ``design.md - Decision 6``. Authority over alert state is granted
per rule ID, and only where the evidence for that rule is both **unanimous and
large enough to mean something**:

    agreement == 100%   AND   scored findings >= support_floor   AND   allowlisted

All three, and the support floor is the load-bearing one. Five of the six
eligible rules in this corpus fire exactly once, so an agreement-only gate would
hand a rule permanent unsupervised dismissal authority on a single case going the
right way — five sixths of the eligible ruleset unlocked by coin flips landing
well. ``k = 5`` is a judgment rather than a derivation: small enough to be
reachable, large enough that unanimity is not cheap.

The allowlist in ``autonomy.json`` is necessary and **not sufficient**. Evidence
is re-checked at run time against a scoring report, so a rule that was granted
authority and has since disagreed loses it without anyone remembering to edit the
file. That inverts the usual failure: the allowlist can only ever narrow what the
evidence permits, never widen it.

On today's corpus the allowlist is empty and no rule could qualify anyway — the
largest, ``AWS-0164``, is n=2. Every ``not-applicable`` verdict therefore travels
to a human as an issue and the alert stays open behind it, which is the correct
outcome and a better claim than an auto-dismissal justified by n=1.

Dismissal is reversible and stays visible: a dismissed alert is still listed
under ``--state dismissed`` and ``--reopen`` puts it back. Nothing here deletes
anything.

Usage::

    autonomy.py --verdicts run.json --evidence score.json          # report only
    autonomy.py --verdicts run.json --evidence score.json --apply
    autonomy.py --reopen 12 --reason "evidence withdrawn"
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
POLICY_PATH = HERE / "autonomy.json"

# The one verdict that could ever justify closing an alert. The other three say
# the finding is real or undecided, and none of them is a reason to stop looking
# at it.
DISMISSIBLE_VERDICT = "not-applicable"

# GitHub's fixed vocabulary for why an alert was closed. A finding judged not
# applicable here is not a scanner error, so it is not a false positive.
DISMISSED_REASON = "won't fix"

ALERTS_ENDPOINT = "/repos/:owner/:repo/code-scanning/alerts"

DISMISS = "dismiss"
PROPOSE = "propose"

# Why authority was withheld. These are the spec's three cases plus the two that
# are not about the rule at all, kept distinct because "never measured" and
# "measured and disagreed" call for different responses from a human reading the
# report.
NEVER_SCORED = "rule has never been scored against the fixture"
BELOW_AGREEMENT = "rule scored below full agreement"
BELOW_SUPPORT = "rule agreed on every case but over too few findings"
NOT_GRANTED = "rule qualifies but has not been granted; granting is an explicit change"
NOT_DISMISSIBLE = "verdict is not `not-applicable`"
NO_ALERT = "no single alert joins to this finding"
UNSUPPORTED_GRANT = "rule is allowlisted but the evidence no longer supports it"


def load_policy(path: pathlib.Path = POLICY_PATH) -> dict[str, Any]:
    """The reviewable half of the ratchet: a file, in a diff, with a floor."""
    with open(path, encoding="utf-8") as handle:
        policy = json.load(handle)
    floor = policy.get("support_floor")
    if not isinstance(floor, int) or floor <= 1:
        raise SystemExit(
            f"support_floor must be an integer greater than 1, so that full agreement "
            f"over a single case never confers authority; got {floor!r}"
        )
    return policy


def allowlisted_rules(policy: dict[str, Any]) -> list[str]:
    return [entry["rule_id"] for entry in policy.get("allowlist", [])]


def evidence_for(rule_id: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
    """What a scoring report says about one rule, if it says anything."""
    return (evidence.get("per_rule") or {}).get(rule_id)


def qualifies(rule_id: str, evidence: dict[str, Any], floor: int) -> tuple[bool, str]:
    """Whether the measurement alone would permit autonomy, and why not if not."""
    measured = evidence_for(rule_id, evidence)
    if measured is None or not measured.get("scored"):
        return False, NEVER_SCORED
    if measured.get("agreement") != 1:
        return False, BELOW_AGREEMENT
    if measured["scored"] < floor:
        return False, BELOW_SUPPORT
    return True, ""


def authority(rule_id: str, evidence: dict[str, Any], policy: dict[str, Any]) -> tuple[bool, str]:
    """Whether this rule may dismiss, requiring evidence *and* an explicit grant.

    Order matters for the message rather than for the answer: a human reading
    "allowlisted but unsupported" needs to know the grant is stale, which is not
    the same problem as a rule nobody has granted yet.
    """
    floor = policy["support_floor"]
    permitted, why_not = qualifies(rule_id, evidence, floor)
    granted = rule_id in allowlisted_rules(policy)

    if granted and not permitted:
        return False, UNSUPPORTED_GRANT
    if not permitted:
        return False, why_not
    if not granted:
        return False, NOT_GRANTED
    return True, ""


def audit(policy: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Check the allowlist against the evidence, in both directions."""
    floor = policy["support_floor"]
    scored = evidence.get("per_rule") or {}
    granted = allowlisted_rules(policy)
    return {
        "support_floor": floor,
        "allowlist": granted,
        "unsupported_grants": [
            rule for rule in granted if not qualifies(rule, evidence, floor)[0]
        ],
        # Reported, never acted on: widening the allowlist is a human's diff.
        "qualifying_not_granted": sorted(
            rule for rule in scored if qualifies(rule, evidence, floor)[0] and rule not in granted
        ),
    }


def decide(
    verdicts: list[dict[str, Any]],
    evidence: dict[str, Any],
    policy: dict[str, Any],
    alert_numbers: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """One decision per verdict: dismiss the alert, or leave it for a human.

    Every path that is not `dismiss` leaves alert state untouched, and says why
    in terms a human can act on.
    """
    alert_numbers = alert_numbers or {}
    decisions: list[dict[str, Any]] = []

    for record in verdicts:
        rule_id = record.get("rule_id") or record.get("key", "").split(":", 1)[0]
        decision = {
            "key": record.get("key", ""),
            "rule_id": rule_id,
            "verdict": record.get("verdict"),
            "alert": alert_numbers.get(record.get("key", "")),
            "action": PROPOSE,
        }

        if record.get("verdict") != DISMISSIBLE_VERDICT:
            decision["reason"] = NOT_DISMISSIBLE
        else:
            permitted, why_not = authority(rule_id, evidence, policy)
            if not permitted:
                decision["reason"] = why_not
            elif decision["alert"] is None:
                decision["reason"] = NO_ALERT
            else:
                decision["action"] = DISMISS
                decision["reason"] = ""
        decisions.append(decision)

    return decisions


def dismissal_comment(record: dict[str, Any]) -> str:
    """What is written onto the alert, so the closure explains itself.

    An alert closed with no reasoning is the failure mode this whole capability
    exists to avoid, so the rationale travels with the act rather than living
    only in a run artifact.
    """
    rationale = (record.get("rationale") or "").strip()
    return (
        f"{rationale}\n\n"
        f"Dismissed automatically for rule {record.get('rule_id', '')}, which has been "
        f"granted autonomous dismissal under the ratchet in "
        f"openspec/changes/add-iac-security-triage/design.md - Decision 6. "
        f"Finding key: {record.get('key', '')}. Reopen this alert to withdraw the closure."
    )


def gh_json(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def patch_alert(number: int, fields: dict[str, str]) -> Any:
    args = ["gh", "api", "--method", "PATCH", f"{ALERTS_ENDPOINT}/{number}"]
    for name, value in fields.items():
        args += ["-f", f"{name}={value}"]
    return gh_json(args)


def dismiss_alert(number: int, comment: str) -> Any:
    return patch_alert(
        number,
        {"state": "dismissed", "dismissed_reason": DISMISSED_REASON, "dismissed_comment": comment},
    )


def reopen_alert(number: int) -> Any:
    """Undo a dismissal. The alert was never gone; this makes it current again."""
    return patch_alert(number, {"state": "open"})


def alert_join_key(rule_id: str, path: str, start_line: Any) -> tuple[str, str, Any]:
    """What identifies an alert to a normalised record.

    Not the finding key: an alert does not carry one. Rule, path and line are
    unique across every first-party finding in this corpus — the only collisions
    are the vendored `AWS-0104` pairs — and this join is only ever asked about
    eligible findings.
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


def alert_for(record: dict[str, Any], index: dict[tuple, list[dict[str, Any]]]) -> dict | None:
    """The single alert a record joins to, or ``None`` if that is ambiguous."""
    join = alert_join_key(record["rule_id"], record["code_path"], record["start_line"])
    matches = index.get(join, [])
    return matches[0] if len(matches) == 1 else None


def alert_numbers(findings: dict[str, Any], alerts: list[dict[str, Any]]) -> dict[str, int]:
    """Finding key -> alert number, for the findings that join to exactly one."""
    index = index_alerts(alerts)
    numbers: dict[str, int] = {}
    for record in findings.get("eligible", []):
        alert = alert_for(record, index)
        if alert is not None:
            numbers[record["key"]] = alert["number"]
    return numbers


def load(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verdicts", help="verdict records from collect_verdicts.py")
    parser.add_argument(
        "--evidence",
        help="a scoring report shaped {'per_rule': {rule_id: {scored, agreed, agreement}}}; "
        "without it nothing is dismissible",
    )
    parser.add_argument("--findings", help="normalised findings, to join keys to alerts")
    parser.add_argument("--alerts", help="alerts JSON; reads `gh` when omitted")
    parser.add_argument("--policy", default=str(POLICY_PATH))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the dismissals; without it nothing is written",
    )
    parser.add_argument("--reopen", type=int, metavar="ALERT", help="reopen a dismissed alert")
    args = parser.parse_args(argv)

    policy = load_policy(pathlib.Path(args.policy))

    if args.reopen is not None:
        reopen_alert(args.reopen)
        print(f"reopened alert {args.reopen}", file=sys.stderr)
        return 0

    if not args.verdicts:
        parser.error("--verdicts is required unless --reopen is given")

    verdicts = load(args.verdicts)
    # No evidence means no rule can qualify, which is the safe reading rather
    # than an error: a run before any scoring has happened should propose
    # everything, not refuse to run.
    evidence = load(args.evidence) if args.evidence else {}

    numbers: dict[str, int] = {}
    if args.findings:
        findings = load(args.findings)
        alerts = load(args.alerts) if args.alerts else gh_json(
            ["gh", "api", ALERTS_ENDPOINT, "--paginate"]
        )
        numbers = alert_numbers(findings, alerts)

    checks = audit(policy, evidence)
    decisions = decide(verdicts, evidence, policy, numbers)
    by_key = {record.get("key"): record for record in verdicts}

    for rule in checks["unsupported_grants"]:
        print(f"error: {rule} is allowlisted but the evidence no longer supports it", file=sys.stderr)

    applied: list[dict[str, Any]] = []
    for decision in decisions:
        if decision["action"] != DISMISS:
            continue
        if args.apply:
            dismiss_alert(decision["alert"], dismissal_comment(by_key[decision["key"]]))
            print(f"dismissed alert {decision['alert']} for {decision['key']}", file=sys.stderr)
        applied.append(decision)

    report = {
        "applied": args.apply,
        "policy": checks,
        "dismissed": applied,
        "proposed": [d for d in decisions if d["action"] == PROPOSE],
    }
    print(json.dumps(report, indent=2))
    return 1 if checks["unsupported_grants"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
