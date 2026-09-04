"""The fixed triage vocabulary.

Defined once here so the verdict collector and the triage personality cannot
drift apart. The verdict classes are those in `docs/design/iac-security-triage.md
- Decisions that are load-bearing in the code`.
"""

from __future__ import annotations

# verdict -> what it means, shown to whoever is labelling.
VERDICTS: dict[str, str] = {
    "not-applicable": "Not applicable here, or a risk this system knowingly accepts",
    "real-mechanical": "A real problem whose fix is mechanical",
    "real-judgment": "A real problem whose fix needs human judgment",
    "undetermined": "Not decidable from the available context",
}

# Ownership is decided by path, not by triage, so it is not a verdict. Vendored
# findings carry this instead.
UPSTREAM = "upstream"
