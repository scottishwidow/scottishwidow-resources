"""The fixed triage vocabulary.

Defined once here so the labelling worksheet, the ground-truth fixture schema
and the triage personality cannot drift apart. The verdict classes are those in
`specs/iac-security-triage/spec.md - Every triaged finding receives a verdict
with a rationale`.
"""

from __future__ import annotations

# verdict -> what it means, shown to whoever is labelling.
VERDICTS: dict[str, str] = {
    "not-applicable": "Not applicable here, or a risk this system knowingly accepts",
    "real-mechanical": "A real problem whose fix is mechanical",
    "real-judgment": "A real problem whose fix needs human judgment",
    "undetermined": "Not decidable from the available context",
}

# How hard the labeller found the call. Recorded so that disagreement on an easy
# finding is distinguishable from disagreement on a hard one (design.md,
# Decision 5).
DIFFICULTIES: dict[str, str] = {
    "easy": "The call was obvious from the finding and the repository's docs",
    "hard": "The call required weighing context, or could reasonably go the other way",
}

# Ownership is decided by path, not by triage, so it is not a verdict. Vendored
# findings carry this instead.
UPSTREAM = "upstream"
