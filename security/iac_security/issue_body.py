"""Parse a triage verdict out of a GitHub issue body.

An alert that is left open has nowhere to record a rationale — GitHub's code
scanning API accepts a comment only alongside a dismissal. The verdict for such a
finding therefore lives on an issue linked to the alert, and this module is the
reader for it.

The issue is not a second verdict store in the sense `design.md - Decision 4`
rejects: it is where the verdict for an open alert is recorded in the first
place, and it is joined back to the finding by the key in its own body rather
than by anything restated here.

The reverse join — issue back to alert — has no other path: a finding key
never appears in alert state, so the issue's **Alert** row, written by the
filer at filing time, is the only record of which alert an issue was filed
for (`CONTEXT.md` — Tracker item).
"""

from __future__ import annotations

import re
from typing import Any

import vocabulary

# The identity row of the issue template. This is what joins an issue to a
# finding; nothing else in the body is load-bearing for the join.
KEY_ROW = re.compile(r"\|\s*\*\*Key\*\*\s*\|\s*`([^`]+)`\s*\|")

# The second identity row, beside Key: the code scanning alert this finding was
# filed for. There is no other path from an issue back to its alert -- a
# finding key never appears in alert state -- so this is the whole of that
# join (`CONTEXT.md` — Tracker item). Absent on a body filed before this row
# existed, or one no matching alert was resolved for; read back as `None`
# rather than an error either way.
ALERT_ROW = re.compile(r"\|\s*\*\*Alert\*\*\s*\|\s*#(\d+)\s*\|")

# Repo-relative paths cited as the basis for a verdict. Narrowed to `.tf` files
# under the two roots the Terraform corpus draws from (ADR-0008): the agent's
# only input beyond the finding is that corpus, so a document path is not
# evidence -- it is a citation of something the agent was never shown.
EVIDENCE_PATH = re.compile(r"\b((?:live|modules)/[\w./-]+\.tf)\b")

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def section(body: str, heading: str) -> str:
    """The text under a ``## heading``, up to the next heading or rule."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|^---\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1) if match else ""


def filled(text: str) -> str:
    """Section text with template prompts removed.

    The template carries its instructions as HTML comments, so a section still
    holding only its prompt is empty rather than answered.
    """
    return HTML_COMMENT.sub("", text).strip()


def parse_evidence(text: str) -> list[str]:
    """Repo-relative paths cited under Evidence, in the order they appear."""
    seen: dict[str, None] = {}
    for match in EVIDENCE_PATH.finditer(filled(text)):
        seen.setdefault(match.group(1), None)
    return list(seen)


def parse(body: str) -> dict[str, Any] | None:
    """Read one issue body, or ``None`` if it carries no finding key.

    A body whose Verdict section is still the unanswered template prompt yields a
    record with an empty verdict; the caller reports it as untriaged rather than
    inventing one.
    """
    key_match = KEY_ROW.search(body)
    if not key_match:
        return None

    alert_match = ALERT_ROW.search(body)

    return {
        "key": key_match.group(1),
        "alert": int(alert_match.group(1)) if alert_match else None,
        "verdict": filled(section(body, "Verdict")).strip("`").strip(),
        "rationale": filled(section(body, "Rationale")),
        "evidence": parse_evidence(section(body, "Evidence")),
    }


def known_verdict(verdict: str) -> bool:
    return verdict in vocabulary.VERDICTS
