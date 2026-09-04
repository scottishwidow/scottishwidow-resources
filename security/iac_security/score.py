#!/usr/bin/env python3
"""Score automated verdicts against the ground-truth fixture.

Reports agreement per rule, each figure alongside the number of findings it was
computed over. The count is not decoration: eight of the ten first-party rules in
this corpus fire exactly once, so an agreement figure without its support is a
coin flip reported as a measurement (`design.md - Decision 5`).

Two exclusions, both of which are reported rather than folded into the numbers:

- **A rule absent from the fixture** is not scored. Counting an unlabelled finding
  as agreement is how a scorer flatters itself; the rule is flagged as needing a
  human verdict instead.
- **An entry whose verdict was not written by a human** cannot score the thing
  that wrote it. Those entries are excluded whatever they say, so a fixture that
  has been partly bootstrapped by a model still yields an honest figure over the
  part that has not.

Usage::

    score.py --run verdicts.json                 # against fixtures/ground-truth.yaml
    score.py --run verdicts.json --fixture other.yaml
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
from typing import Any

import yaml

import fixture_schema
import issue_body

HERE = pathlib.Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "ground-truth.yaml"


def load_fixture(path: pathlib.Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        fixture = yaml.safe_load(handle)
    errors = fixture_schema.validate(fixture)
    if errors:
        raise SystemExit("fixture is invalid:\n  " + "\n  ".join(errors))
    return fixture


def scorable(entry: dict[str, Any]) -> bool:
    """Only a human-authored verdict can serve as ground truth."""
    return entry.get("verdict_author") == issue_body.HUMAN


def score(fixture: dict[str, Any], run: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare a triage run's verdicts against the fixture."""
    entries = {entry["key"]: entry for entry in fixture["entries"]}
    scorable_keys = {key for key, entry in entries.items() if scorable(entry)}
    fixture_rules = {entry["rule_id"] for entry in entries.values() if scorable(entry)}

    per_rule: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"scored": 0, "agreed": 0, "disagreements": []}
    )
    unscored_rules: set[str] = set()
    excluded_non_human: list[str] = []
    unknown_keys: list[str] = []

    for result in run:
        key = result["key"]
        entry = entries.get(key)
        if entry is None:
            unknown_keys.append(key)
            if result.get("rule_id") not in fixture_rules:
                unscored_rules.add(result.get("rule_id", ""))
            continue
        if key not in scorable_keys:
            excluded_non_human.append(key)
            continue

        rule = entry["rule_id"]
        bucket = per_rule[rule]
        bucket["scored"] += 1
        if result.get("verdict") == entry["verdict"]:
            bucket["agreed"] += 1
        else:
            bucket["disagreements"].append(
                {"key": key, "expected": entry["verdict"], "got": result.get("verdict")}
            )

    for bucket in per_rule.values():
        bucket["agreement"] = (
            round(bucket["agreed"] / bucket["scored"], 4) if bucket["scored"] else None
        )

    scored_keys = {r["key"] for r in run} & scorable_keys
    total_scored = sum(b["scored"] for b in per_rule.values())
    total_agreed = sum(b["agreed"] for b in per_rule.values())

    return {
        "fixture_entries": len(entries),
        "scorable_entries": len(scorable_keys),
        "per_rule": dict(sorted(per_rule.items())),
        "overall": {
            "scored": total_scored,
            "agreed": total_agreed,
            "agreement": round(total_agreed / total_scored, 4) if total_scored else None,
        },
        "excluded_non_human": sorted(set(excluded_non_human)),
        "unscored_rules": sorted(r for r in unscored_rules if r),
        "unknown_keys": sorted(set(unknown_keys)),
        "not_covered_by_run": sorted(scorable_keys - scored_keys),
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        f"scorable fixture entries: {report['scorable_entries']} "
        f"of {report['fixture_entries']}",
        "",
        "agreement by rule (figure, then the findings it covers):",
    ]
    if not report["per_rule"]:
        lines.append("  none — no scorable finding was covered by this run")
    for rule, bucket in report["per_rule"].items():
        lines.append(
            f"  {rule}  {bucket['agreement']:.0%}  over n={bucket['scored']}"
            + ("" if bucket["agreement"] == 1 else f"  ({len(bucket['disagreements'])} differ)")
        )
    overall = report["overall"]
    if overall["agreement"] is not None:
        lines.append(f"  overall  {overall['agreement']:.0%}  over n={overall['scored']}")

    for label, items in (
        ("excluded, verdict not human-authored", report["excluded_non_human"]),
        ("unscored — rule absent from the fixture, needs a human verdict", report["unscored_rules"]),
        ("in the run but not in the fixture", report["unknown_keys"]),
        ("in the fixture but not in the run", report["not_covered_by_run"]),
    ):
        if items:
            lines.extend(["", f"{label}:"] + [f"  {item}" for item in items])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="JSON list of {key, rule_id, verdict}")
    parser.add_argument("--fixture", default=str(FIXTURE))
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    fixture = load_fixture(pathlib.Path(args.fixture))
    with open(args.run, encoding="utf-8") as handle:
        run = json.load(handle)

    report = score(fixture, run)
    print(json.dumps(report, indent=2) if args.json else render(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
