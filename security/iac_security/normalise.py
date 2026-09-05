#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
from typing import Any, Iterator

FIRST_PARTY = "first-party"
VENDORED = "vendored"

# A disposition, not a verdict: `vocabulary.py` holds the verdicts.
ELIGIBLE = "eligible"
BELOW_THRESHOLD = "below-threshold"
UPSTREAM = "upstream"

# Trivy's severity ladder, least to most severe.
SEVERITY_ORDER = ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")

# The threshold is configuration, not a literal in the partition logic, so
# raising or lowering it is a reviewable diff.
CONFIG_PATH = pathlib.Path(__file__).resolve().parent / "config.json"

# A path anywhere under a resolved module cache belongs to whoever publishes the
# module, not to this repository.
VENDORED_PATH_MARKERS = (".terraform/modules/",)

FIRST_PARTY_PREFIXES = ("live/", "modules/")

RESOURCE_DECLARATION = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"')


def iter_findings(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for result in report.get("Results") or []:
        target = result.get("Target", "")
        for misconf in result.get("Misconfigurations") or []:
            if misconf.get("Status", "FAIL") != "FAIL":
                continue
            yield target, misconf


def cause_lines(misconf: dict[str, Any]) -> list[dict[str, Any]]:
    lines = (misconf.get("CauseMetadata") or {}).get("Code", {}).get("Lines") or []
    return [
        {"number": line.get("Number"), "content": (line.get("Content") or "").rstrip()}
        for line in lines
    ]


def parse_resource_address(lines: list[dict[str, Any]]) -> str:
    """``CauseMetadata.Resource`` is the module address, not this; recovered from the declaration line instead."""
    for line in lines:
        match = RESOURCE_DECLARATION.match(line["content"])
        if match:
            return f"{match.group(1)}.{match.group(2)}"
    return ""


def owner_path(target: str, misconf: dict[str, Any]) -> str:
    occurrences = (misconf.get("CauseMetadata") or {}).get("Occurrences") or []
    for occurrence in occurrences:
        filename = occurrence.get("Filename")
        if filename:
            return filename
    return target


def classify(path: str) -> tuple[str, bool]:
    """An unrecognised path is treated as first-party, so nothing escapes triage by being unexpected."""
    if any(marker in path for marker in VENDORED_PATH_MARKERS):
        return VENDORED, True
    if any(path.startswith(prefix) for prefix in FIRST_PARTY_PREFIXES):
        return FIRST_PARTY, True
    return FIRST_PARTY, False


def load_threshold(path: pathlib.Path = CONFIG_PATH) -> str:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["severity_threshold"]


def meets_threshold(severity: str, threshold: str) -> bool:
    """A severity Trivy never emits is treated as meeting the threshold: nothing escapes by being unexpected."""
    if severity not in SEVERITY_ORDER:
        return True
    return SEVERITY_ORDER.index(severity) >= SEVERITY_ORDER.index(threshold)


def triage_status(ownership: str, severity: str, threshold: str) -> str:
    """Ownership first, then severity: a vendored finding is excluded whatever its severity."""
    if ownership == VENDORED:
        return UPSTREAM
    return ELIGIBLE if meets_threshold(severity, threshold) else BELOW_THRESHOLD


def finding_key(rule_id: str, module_address: str, resource_address: str) -> str:
    """Deliberately not a hash: this key appears in issue bodies, where readable beats compact."""
    return f"{rule_id}:{module_address}:{resource_address}"


def finding_key_of(misconf: dict[str, Any]) -> str:
    """The one derivation of a finding's identity from a Trivy misconfiguration; every caller uses it."""
    cause = misconf.get("CauseMetadata") or {}
    return finding_key(
        misconf.get("ID", ""),
        cause.get("Resource") or "",
        parse_resource_address(cause_lines(misconf)),
    )


def duplicate_keys(records: list[dict[str, Any]]) -> list[str]:
    """First-party keys claimed by more than one finding; those findings would share a verdict."""
    counts = collections.Counter(
        record["key"] for record in records if record["ownership"] == FIRST_PARTY
    )
    return sorted(key for key, count in counts.items() if count > 1)


def normalise(report: dict[str, Any], threshold: str | None = None) -> dict[str, Any]:
    if threshold is None:
        threshold = load_threshold()
    records: list[dict[str, Any]] = []

    for target, misconf in iter_findings(report):
        cause = misconf.get("CauseMetadata") or {}
        lines = cause_lines(misconf)
        rule_id = misconf.get("ID", "")
        module_address = cause.get("Resource") or ""
        resource_address = parse_resource_address(lines)
        path = owner_path(target, misconf)
        ownership, recognised = classify(path)
        severity = misconf.get("Severity", "")
        resource_type, _, resource_name = resource_address.partition(".")

        records.append(
            {
                "key": finding_key_of(misconf),
                "rule_id": rule_id,
                "title": misconf.get("Title", ""),
                "severity": severity,
                "message": misconf.get("Message", ""),
                "resolution": misconf.get("Resolution", ""),
                "primary_url": misconf.get("PrimaryURL", ""),
                "module_address": module_address,
                "resource_type": resource_type,
                "resource_name": resource_name,
                "resource_address": resource_address,
                "owner_path": path,
                "code_path": target,
                "start_line": cause.get("StartLine"),
                "end_line": cause.get("EndLine"),
                "ownership": ownership,
                "ownership_recognised": recognised,
                "triage_status": triage_status(ownership, severity, threshold),
                "code": lines,
            }
        )

    unrecognised = sorted(
        {record["owner_path"] for record in records if not record["ownership_recognised"]}
    )

    return {
        "severity_threshold": threshold,
        "eligible": [r for r in records if r["triage_status"] == ELIGIBLE],
        "below_threshold": [r for r in records if r["triage_status"] == BELOW_THRESHOLD],
        "vendored": [r for r in records if r["triage_status"] == UPSTREAM],
        "unrecognised_locations": unrecognised,
        "duplicate_first_party_keys": duplicate_keys(records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalise Trivy config-scan JSON into one record per finding."
    )
    parser.add_argument(
        "report",
        nargs="?",
        help="Trivy config JSON report; reads stdin when omitted",
    )
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    if args.report:
        with open(args.report, encoding="utf-8") as handle:
            report = json.load(handle)
    else:
        report = json.load(sys.stdin)

    normalised = normalise(report)

    for path in normalised["unrecognised_locations"]:
        print(f"warning: unrecognised location, treating as first-party: {path}", file=sys.stderr)
    for key in normalised["duplicate_first_party_keys"]:
        print(f"warning: first-party key claimed by more than one finding: {key}", file=sys.stderr)

    rendered = json.dumps(normalised, indent=2, sort_keys=False) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
