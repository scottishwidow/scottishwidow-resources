#!/usr/bin/env python3
"""Normalise Trivy config-scan JSON into one record per finding.

Reads a Trivy ``config --format json`` report and emits a single JSON object
partitioning the findings by ownership::

    {"first_party": [...], "vendored": [...], "unrecognised_locations": [...]}

Identity follows ``design.md - Decision 3``: a core of rule ID, module address
and resource address, plus an ordinal that separates sibling findings the core
cannot. Ownership follows ``Decision 2`` and is a path check, never a judgment.

Usage::

    trivy config --format json . | normalise.py
    normalise.py fixtures/baseline-scan.json -o normalised.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any, Iterator

FIRST_PARTY = "first-party"
VENDORED = "vendored"

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


def fingerprint(core: str, ordinal: int) -> str:
    return hashlib.sha256(f"{core}:{ordinal}".encode()).hexdigest()


def normalise(report: dict[str, Any]) -> dict[str, Any]:
    """Turn a Trivy report into ownership-partitioned, fingerprinted records."""
    records: list[dict[str, Any]] = []

    for sequence, (target, misconf) in enumerate(iter_findings(report)):
        cause = misconf.get("CauseMetadata") or {}
        lines = cause_lines(misconf)
        module_address = cause.get("Resource") or ""
        resource_address = parse_resource_address(lines)
        path = owner_path(target, misconf)
        ownership, recognised = classify(path)
        resource_type, _, resource_name = resource_address.partition(".")

        records.append(
            {
                "core": f"{misconf.get('ID', '')}|{module_address}|{resource_address}",
                "sequence": sequence,
                "record": {
                    "fingerprint": None,  # filled in once ordinals are known
                    "rule_id": misconf.get("ID", ""),
                    "title": misconf.get("Title", ""),
                    "severity": misconf.get("Severity", ""),
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
                    "code": lines,
                },
            }
        )

    _assign_ordinals(records)

    first_party = [
        item["record"] for item in records if item["record"]["ownership"] == FIRST_PARTY
    ]
    vendored = [
        item["record"] for item in records if item["record"]["ownership"] == VENDORED
    ]
    unrecognised = sorted(
        {
            item["record"]["owner_path"]
            for item in records
            if not item["record"]["ownership_recognised"]
        }
    )

    return {
        "first_party": first_party,
        "vendored": vendored,
        "unrecognised_locations": unrecognised,
    }


def _assign_ordinals(records: list[dict[str, Any]]) -> None:
    """Number findings that share a core, ordered by position, then fingerprint."""
    by_core: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        by_core.setdefault(item["core"], []).append(item)

    for core, siblings in by_core.items():
        ordered = sorted(
            siblings,
            key=lambda item: (
                item["record"]["start_line"] if item["record"]["start_line"] is not None else -1,
                item["record"]["end_line"] if item["record"]["end_line"] is not None else -1,
                item["sequence"],
            ),
        )
        for ordinal, item in enumerate(ordered):
            item["record"]["fingerprint"] = fingerprint(core, ordinal)


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

    rendered = json.dumps(normalised, indent=2, sort_keys=False) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
