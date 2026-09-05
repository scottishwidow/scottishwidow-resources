#!/usr/bin/env python3
"""The patch gate: a deterministic accept-or-reject decision on a remediation patch.

See `docs/design/iac-security-triage.md` — "A patch is filtered, never accepted,
by anything other than a human." This module performs no I/O: the workflow
applies the diff, runs `terraform validate` and `fmt -check`, and re-scans, then
hands the outcomes here as evidence.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Any

import normalise

APPLY = "apply"
PERMITTED_PATHS = "permitted_paths"
TERRAFORM_VALIDATE = "terraform_validate"
TERRAFORM_FMT = "terraform_fmt"
TARGET_REMOVED = "target_removed"
NO_NEW_FINDINGS = "no_new_findings"
ACCEPTED = "accepted"

FILE_HEADER = re.compile(r"^diff --git a/(?P<a>.+) b/(?P<b>.+)$", re.MULTILINE)
NEW_FILE_MARKER = re.compile(r"^(?:new file mode\b|--- /dev/null$)")


@dataclass(frozen=True)
class Decision:
    accepted: bool
    gate: str
    reason: str


@dataclass(frozen=True)
class TouchedFile:
    path: str
    is_new: bool


def touched_files(diff: str) -> list[TouchedFile]:
    """Parsed from the ``diff --git a/... b/...`` header of each file section, not applied."""
    files = []
    for block in re.split(r"(?m)^(?=diff --git )", diff):
        header = FILE_HEADER.match(block)
        if not header:
            continue
        is_new = any(NEW_FILE_MARKER.match(line) for line in block.splitlines())
        files.append(TouchedFile(path=header.group("b"), is_new=is_new))
    return files


def path_is_permitted(touched: TouchedFile, finding: dict[str, Any]) -> bool:
    """The code path, the owner path, or a *new* file beside the code path — not an existing sibling."""
    if touched.path in (finding["code_path"], finding["owner_path"]):
        return True
    return touched.is_new and posixpath.dirname(touched.path) == posixpath.dirname(
        finding["code_path"]
    )


def finding_keys(report: dict[str, Any]) -> set[str]:
    """Every finding key in a scan report, ownership and severity aside — this gate only counts keys."""
    keys = set()
    for _, misconf in normalise.iter_findings(report):
        cause = misconf.get("CauseMetadata") or {}
        resource_address = normalise.parse_resource_address(normalise.cause_lines(misconf))
        keys.add(
            normalise.finding_key(
                misconf.get("ID", ""), cause.get("Resource") or "", resource_address
            )
        )
    return keys


def decide(
    diff: str,
    finding: dict[str, Any],
    pre_scan: dict[str, Any],
    post_scan: dict[str, Any],
    *,
    applies: bool,
    validate_passed: bool,
    fmt_passed: bool,
) -> Decision:
    """The five gates, in order; the first one a patch fails is the whole of the decision."""
    if not applies:
        return Decision(False, APPLY, "the diff does not apply cleanly")

    for touched in touched_files(diff):
        if not path_is_permitted(touched, finding):
            return Decision(
                False,
                PERMITTED_PATHS,
                f"`{touched.path}` is outside the permitted set for {finding['key']}",
            )

    if not validate_passed:
        return Decision(False, TERRAFORM_VALIDATE, "terraform validate fails after the patch")

    if not fmt_passed:
        return Decision(False, TERRAFORM_FMT, "terraform fmt -check fails after the patch")

    key = finding["key"]
    post_keys = finding_keys(post_scan)
    if key in post_keys:
        return Decision(False, TARGET_REMOVED, f"{key} is still present after the patch")

    introduced = sorted(post_keys - finding_keys(pre_scan))
    if introduced:
        return Decision(
            False,
            NO_NEW_FINDINGS,
            "the patch introduces a new finding: " + ", ".join(introduced),
        )

    return Decision(True, ACCEPTED, f"{key} is removed and no new finding is introduced")
