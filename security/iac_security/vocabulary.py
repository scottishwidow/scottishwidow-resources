"""The fixed triage vocabulary.

Defined once here so the ground-truth fixture schema, the scoring tool and
the triage personality cannot drift apart. The verdict classes are those in
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

# Ownership is decided by path, not by triage, so it is not a verdict. Vendored
# findings carry this instead.
UPSTREAM = "upstream"
