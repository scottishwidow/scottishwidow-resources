"""Validate the ground-truth fixture.

The fixture is what every agreement figure is computed against, so a malformed
entry is worse than a missing one: a misspelled verdict silently agrees with
nothing, and an empty rationale is a verdict nobody can audit. Validation is
therefore a gate rather than a lint, and `validate` returns the reasons rather
than a boolean so the caller can print them.

The verdict vocabulary is not restated here. It comes from `vocabulary.py`, which
is also what the triage personality and the scorer read, so the three cannot
drift apart.
"""

from __future__ import annotations

from typing import Any

import issue_body
import vocabulary

REQUIRED_FIELDS = ("key", "rule_id", "verdict", "verdict_author", "rationale", "evidence")

TOP_LEVEL_FIELDS = ("severity_threshold", "exported_at", "entries")


def validate(fixture: Any) -> list[str]:
    """Every reason this fixture is unusable, in the order they were found."""
    errors: list[str] = []

    if not isinstance(fixture, dict):
        return ["fixture is not a mapping"]

    for field in TOP_LEVEL_FIELDS:
        if field not in fixture:
            errors.append(f"missing top-level field: {field}")

    entries = fixture.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries is not a list"]

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"entry {index}"
        if not isinstance(entry, dict):
            errors.append(f"{where}: not a mapping")
            continue

        key = entry.get("key")
        where = f"entry {key!r}" if key else where

        for field in REQUIRED_FIELDS:
            if field not in entry:
                errors.append(f"{where}: missing field {field}")

        if key in seen:
            errors.append(f"{where}: duplicate key")
        elif isinstance(key, str):
            seen.add(key)

        verdict = entry.get("verdict")
        if verdict is not None and verdict not in vocabulary.VERDICTS:
            errors.append(
                f"{where}: unknown verdict {verdict!r}; "
                f"expected one of {', '.join(sorted(vocabulary.VERDICTS))}"
            )

        author = entry.get("verdict_author")
        if author is not None and author not in issue_body.AUTHORS:
            errors.append(
                f"{where}: unknown verdict_author {author!r}; "
                f"expected one of {', '.join(issue_body.AUTHORS)}"
            )

        rationale = entry.get("rationale")
        if isinstance(rationale, str) and not rationale.strip():
            errors.append(f"{where}: empty rationale; a verdict is not recorded without one")
        elif rationale is not None and not isinstance(rationale, str):
            errors.append(f"{where}: rationale is not a string")

        evidence = entry.get("evidence")
        if evidence is not None and (
            not isinstance(evidence, list) or any(not isinstance(p, str) for p in evidence)
        ):
            errors.append(f"{where}: evidence is not a list of paths")

    return errors
