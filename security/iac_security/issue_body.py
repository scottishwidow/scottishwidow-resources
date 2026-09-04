from __future__ import annotations

import re
from typing import Any

import vocabulary

# Joins an issue back to its finding; nothing else in the body is load-bearing for that.
KEY_ROW = re.compile(r"\|\s*\*\*Key\*\*\s*\|\s*`([^`]+)`\s*\|")

# Matches a link, a bare `#42`, or a code span alike; all three read back the same number.
ALERT_ROW = re.compile(r"\|\s*\*\*Alert\*\*\s*\|[^|\n]*?#(\d+)")

# `.tf` files under the corpus roots only: anything else was never shown to the agent.
EVIDENCE_PATH = re.compile(r"\b((?:live|modules)/[\w./-]+\.tf)\b")

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|^---\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1) if match else ""


def filled(text: str) -> str:
    """The template's instructions are HTML comments, so a section holding only its prompt is empty."""
    return HTML_COMMENT.sub("", text).strip()


def parse_evidence(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for match in EVIDENCE_PATH.finditer(filled(text)):
        seen.setdefault(match.group(1), None)
    return list(seen)


def parse(body: str) -> dict[str, Any] | None:
    """`None` if the body carries no finding key; an unanswered Verdict prompt yields an empty verdict."""
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
