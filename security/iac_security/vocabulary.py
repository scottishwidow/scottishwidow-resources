"""Defined once here so the verdict collector and the triage personality cannot drift apart."""

from __future__ import annotations

VERDICTS: dict[str, str] = {
    "not-applicable": "Not applicable here, or a risk this system knowingly accepts",
    "real-mechanical": "A real problem whose fix is mechanical",
    "real-judgment": "A real problem whose fix needs human judgment",
    "undetermined": "Not decidable from the available context",
}

# Named because three modules branch on this one class: it is the outcome of the
# discard rule, and a tracker item carrying it is a finding still awaiting a verdict.
UNDETERMINED = "undetermined"

# Not a verdict: ownership is decided by path, not by triage.
UPSTREAM = "upstream"
