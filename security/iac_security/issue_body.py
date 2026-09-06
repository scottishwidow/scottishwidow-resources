from __future__ import annotations

import re
from typing import Any

import vocabulary

# Joins an issue back to its finding; nothing else in the body is load-bearing for that.
KEY_ROW = re.compile(r"\|\s*\*\*Key\*\*\s*\|\s*`([^`]+)`\s*\|")

# Matches a link, a bare `#42`, or a code span alike; all three read back the same number.
ALERT_ROW = re.compile(r"\|\s*\*\*Alert\*\*\s*\|[^|\n]*?#(\d+)")

# The heading a re-triage comment writes its verdict under, deliberately not `Verdict`:
# `parse` reads the issue body, and one heading for both would let a comment be read as one.
NEW_VERDICT = "New verdict"

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


def comment_verdict(text: str) -> str:
    """The verdict a re-triage comment carries, or empty if it carries none."""
    return filled(section(text, NEW_VERDICT)).strip("`").strip()


def standing_verdict(body: str, comments: list[str] | None = None) -> str:
    """What a tracker item records now: its latest re-triage comment, else its body.

    A comment is what a second verdict on an item arrives as, so an item whose
    body still says `undetermined` may already have been judged.
    """
    verdict = (parse(body) or {}).get("verdict", "")
    for text in comments or []:
        found = comment_verdict(text)
        if found:
            verdict = found
    return verdict


def tracker_items(issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Finding key -> the item that claims it, for issues that carry a key."""
    found: dict[str, dict[str, Any]] = {}
    for issue in issues:
        parsed = parse(issue.get("body") or "")
        if not parsed or parsed["key"] in found:
            continue
        comments = [entry.get("body") or "" for entry in issue.get("comments") or []]
        found[parsed["key"]] = {
            "issue": issue.get("number"),
            # A snapshot taken before the state field was fetched reads as open, which
            # re-triages a closed finding rather than silently dropping a live one.
            "state": str(issue.get("state") or "OPEN").upper(),
            "verdict": standing_verdict(issue.get("body") or "", comments),
        }
    return found


def awaits_a_verdict(item: dict[str, Any]) -> bool:
    """Whether an item's finding is triaged again: `undetermined` is a failure to judge, not a judgment."""
    return item["state"] == "OPEN" and item["verdict"] == vocabulary.UNDETERMINED
