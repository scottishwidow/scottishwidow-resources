"""Defined once here so the verdict collector and the triage personality cannot drift apart."""

from __future__ import annotations

VERDICTS: dict[str, str] = {
    "not-applicable": "Not applicable here, or a risk this system knowingly accepts",
    "real-mechanical": "A real problem whose fix is mechanical",
    "real-judgment": "A real problem whose fix needs human judgment",
    "undetermined": "Not decidable from the available context",
}

# Not a verdict: ownership is decided by path, not by triage.
UPSTREAM = "upstream"
