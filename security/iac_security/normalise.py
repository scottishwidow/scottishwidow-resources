#!/usr/bin/env python3
"""Normalise Trivy config-scan JSON into one record per finding.

Reads a Trivy ``config --format json`` report and emits a single JSON object
partitioning the findings by ownership::

    {"eligible": [...], "below_threshold": [...], "vendored": [...]}

Identity follows ``design.md - Decision 3``: the key is the readable composite
``ruleId:module_address:resource_type.resource_name``. It survives line-number
drift, and it is unique across first-party findings, which is the only place a
key is used to carry a verdict.

The partition follows ``Decision 2`` and runs in two stages, neither of which is
a judgment: ownership by path, then severity against a threshold read from
``config.json``. The order is load-bearing — every ``CRITICAL`` finding in this
repository is vendored, so severity applied alone would admit the eight findings
that can never be fixed here and drop five first-party ones.

Nothing here assigns a verdict. Below-threshold findings are not dismissed:
they stay in the output marked ``below-threshold`` so that they remain published
as open alerts and no downstream step files an issue for them.

Usage::

    trivy config --format json . | normalise.py
    normalise.py fixtures/baseline-scan.json -o normalised.json
"""

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

# What the two deterministic filters decide about a finding, before any model
# sees it. These are dispositions, not verdicts: `vocabulary.py` holds the
# verdicts, and none of them is assigned here.
ELIGIBLE = "eligible"
BELOW_THRESHOLD = "below-threshold"
UPSTREAM = "upstream"

# Trivy's severity ladder, least to most severe.
SEVERITY_ORDER = ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")

# The threshold is configuration, not a literal in the partition logic, so
# raising or lowering it is a reviewable diff (`design.md - Decision 2`).
CONFIG_PATH = pathlib.Path(__file__).resolve().parent / "config.json"

# A path anywhere under a resolved module cache belongs to whoever publishes the
# module, not to this repository.
VENDORED_PATH_MARKERS = (".terraform/modules/",)

# The two roots this repository maintains.
FIRST_PARTY_PREFIXES = ("live/", "modules/")

RESOURCE_DECLARATION = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"')


def iter_findings(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(scan target, misconfiguration)`` for every failing check."""
    for result in report.get("Results") or []:
        target = result.get("Target", "")
        for misconf in result.get("Misconfigurations") or []:
            if misconf.get("Status", "FAIL") != "FAIL":
                continue
            yield target, misconf


def cause_lines(misconf: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the offending code as ``[{"number": int, "content": str}, ...]``."""
    lines = (misconf.get("CauseMetadata") or {}).get("Code", {}).get("Lines") or []
    return [
        {"number": line.get("Number"), "content": (line.get("Content") or "").rstrip()}
        for line in lines
    ]


def parse_resource_address(lines: list[dict[str, Any]]) -> str:
    """Recover ``type.name`` from the cause lines.

    ``CauseMetadata.Resource`` is the *module* address, so the Terraform resource
    address is only available from the declaration inside the cause block.
    """
    for line in lines:
        match = RESOURCE_DECLARATION.match(line["content"])
        if match:
            return f"{match.group(1)}.{match.group(2)}"
    return ""


def owner_path(target: str, misconf: dict[str, Any]) -> str:
    """The path ownership is decided on: where the offending code is instantiated."""
    occurrences = (misconf.get("CauseMetadata") or {}).get("Occurrences") or []
    for occurrence in occurrences:
        filename = occurrence.get("Filename")
        if filename:
            return filename
    return target


def classify(path: str) -> tuple[str, bool]:
    """Partition a path into ``(ownership, recognised)``.

    An unrecognised path is treated as first-party so that nothing escapes triage
    by being in an unexpected place; the caller surfaces it for a human.
    """
    if any(marker in path for marker in VENDORED_PATH_MARKERS):
        return VENDORED, True
    if any(path.startswith(prefix) for prefix in FIRST_PARTY_PREFIXES):
        return FIRST_PARTY, True
    return FIRST_PARTY, False


def load_threshold(path: pathlib.Path = CONFIG_PATH) -> str:
    """Read the severity threshold from configuration."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["severity_threshold"]


def meets_threshold(severity: str, threshold: str) -> bool:
    """Whether a severity is at or above the threshold.

    A severity Trivy has never emitted is treated as meeting the threshold, for
    the same reason an unrecognised path is treated as first-party: nothing
    should escape triage by being unexpected.
    """
    if severity not in SEVERITY_ORDER:
        return True
    return SEVERITY_ORDER.index(severity) >= SEVERITY_ORDER.index(threshold)


def triage_status(ownership: str, severity: str, threshold: str) -> str:
    """Apply the two filters in order: ownership first, then severity.

    Ownership answers "can this repository fix it"; severity answers "is it
    worth the reasoning". A vendored finding is excluded on ownership alone,
    whatever its severity.
    """
    if ownership == VENDORED:
        return UPSTREAM
    return ELIGIBLE if meets_threshold(severity, threshold) else BELOW_THRESHOLD


def finding_key(rule_id: str, module_address: str, resource_address: str) -> str:
    """The readable identity a verdict is recorded against.

    Deliberately not a hash: this key appears in issue bodies, where being able
    to read it is worth more than being able to compute it compactly.
    """
    return f"{rule_id}:{module_address}:{resource_address}"


def duplicate_keys(records: list[dict[str, Any]]) -> list[str]:
    """First-party keys claimed by more than one finding.

    Two findings sharing a key share a verdict, which is correct when they are
    co-located siblings of one resource and wrong otherwise. It never happens on
    first-party code in the current corpus, so it is surfaced rather than
    silently absorbed by an ordinal.
    """
    counts = collections.Counter(
        record["key"] for record in records if record["ownership"] == FIRST_PARTY
    )
    return sorted(key for key, count in counts.items() if count > 1)


def normalise(report: dict[str, Any], threshold: str | None = None) -> dict[str, Any]:
    """Turn a Trivy report into keyed records, partitioned for triage."""
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
                "key": finding_key(rule_id, module_address, resource_address),
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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
