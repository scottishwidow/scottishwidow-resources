"""The patch gate: the deterministic filter a remediation patch passes before it reaches review.

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
TARGET_REMOVAL = "target_removal"
NEW_FINDINGS = "new_findings"
PASSED = "passed"

FILE_HEADER_PREFIX = "diff --git "
FILE_HEADER = re.compile(
    rf"^{FILE_HEADER_PREFIX}a/(?P<a>.+) b/(?P<b>.+)$", re.MULTILINE
)
NEW_FILE_MARKER = re.compile(r"^(?:new file mode\b|--- /dev/null$)")
DELETED_FILE_MARKER = re.compile(r"^(?:deleted file mode\b|\+\+\+ /dev/null$)")
RENAME_MARKER = re.compile(r"^rename (?:from|to) ")


class UnreadableHeader(Exception):
    """A file section whose header names no path this gate can read.

    Git quotes a path holding a non-ASCII byte, and the quoted form is left
    undecoded on purpose: remediation touches an existing `.tf` path or a new
    sibling of one, so a path this gate cannot read is a patch that should not
    reach review.
    """

    def __init__(self, header: str) -> None:
        super().__init__(header)
        self.header = header


@dataclass(frozen=True)
class Decision:
    passed: bool
    gate: str
    reason: str


@dataclass(frozen=True)
class Evidence:
    """What the workflow observed by running the patch; the gate reads it and runs nothing itself."""

    applies: bool
    validate_passed: bool
    fmt_passed: bool


@dataclass(frozen=True)
class TouchedFile:
    path: str
    source_path: str
    is_new: bool
    is_deleted: bool
    is_renamed: bool


def touched_files(diff: str) -> list[TouchedFile]:
    """Parsed from the ``diff --git a/... b/...`` header of each file section, not applied.

    Raises ``UnreadableHeader`` rather than skipping a section it cannot parse,
    so an unreadable path reaches the permitted-paths gate instead of passing
    unexamined.
    """
    files = []
    for block in re.split(rf"(?m)^(?={FILE_HEADER_PREFIX})", diff):
        if not block.startswith(FILE_HEADER_PREFIX):
            continue
        header = FILE_HEADER.match(block)
        if not header:
            raise UnreadableHeader(block.splitlines()[0])
        lines = block.splitlines()
        files.append(
            TouchedFile(
                path=header.group("b"),
                source_path=header.group("a"),
                is_new=any(NEW_FILE_MARKER.match(line) for line in lines),
                is_deleted=any(DELETED_FILE_MARKER.match(line) for line in lines),
                is_renamed=any(RENAME_MARKER.match(line) for line in lines),
            )
        )
    return files


def path_is_permitted(touched: TouchedFile, finding: dict[str, Any]) -> bool:
    """The code path, the owner path, or a *new* file beside the code path — not an existing sibling."""
    if touched.path in (finding["code_path"], finding["owner_path"]):
        return True
    # Newness is the diff's own claim; a diff that claims it falsely fails to apply, which the apply gate catches.
    return touched.is_new and posixpath.dirname(touched.path) == posixpath.dirname(
        finding["code_path"]
    )


def finding_keys(report: dict[str, Any]) -> set[str]:
    """Every finding key in a scan report, ownership and severity aside — this gate only counts keys."""
    return {
        normalise.finding_key_of(misconf) for _, misconf in normalise.iter_findings(report)
    }


def decide(
    diff: str,
    finding: dict[str, Any],
    pre_scan: dict[str, Any],
    post_scan: dict[str, Any],
    evidence: Evidence,
) -> Decision:
    """The five gates, in order; the first one a patch fails is the whole of the decision."""
    if not evidence.applies:
        return Decision(False, APPLY, "the diff does not apply cleanly")

    try:
        touched = touched_files(diff)
    except UnreadableHeader as unreadable:
        return Decision(
            False,
            PERMITTED_PATHS,
            f"`{unreadable.header}` names no path this gate can read",
        )
    if not touched:
        return Decision(False, APPLY, "the diff changes nothing")

    for touched_file in touched:
        if touched_file.is_deleted:
            return Decision(
                False,
                PERMITTED_PATHS,
                f"`{touched_file.path}` is deleted, which no remediation permits",
            )
        # A rename carries neither marker above, so the source path's removal is otherwise invisible.
        if touched_file.is_renamed:
            return Decision(
                False,
                PERMITTED_PATHS,
                f"`{touched_file.source_path}` is renamed away, which no remediation permits",
            )
        if not path_is_permitted(touched_file, finding):
            return Decision(
                False,
                PERMITTED_PATHS,
                f"`{touched_file.path}` is outside the permitted set for {finding['key']}",
            )

    if not evidence.validate_passed:
        return Decision(False, TERRAFORM_VALIDATE, "terraform validate fails after the patch")

    if not evidence.fmt_passed:
        return Decision(False, TERRAFORM_FMT, "terraform fmt -check fails after the patch")

    key = finding["key"]
    post_keys = finding_keys(post_scan)
    if key in post_keys:
        return Decision(False, TARGET_REMOVAL, f"{key} is still present after the patch")

    introduced = sorted(post_keys - finding_keys(pre_scan))
    if introduced:
        return Decision(
            False,
            NEW_FINDINGS,
            "the patch introduces a new finding: " + ", ".join(introduced),
        )

    return Decision(True, PASSED, f"{key} is removed and no new finding is introduced")
