# Fixtures

`baseline-scan.json` is the raw output of `trivy config --format json .` run against
the repository at the point this capability was introduced (main@06680c9). It is the
corpus referenced throughout `openspec/changes/add-iac-security-triage/design.md` and
`specs/iac-security-triage/spec.md`: 20 findings across 11 rule IDs.

It is a fixture, not a live artifact — regenerate deliberately (`trivy config --format
json .` from the repo root) rather than overwriting it as part of routine scans.

`ground-truth.yaml` holds the verdicts for the 7 triage-eligible findings — the
first-party ones at `HIGH` or above, not all 12 first-party ones. It is written by
`export_fixture.py` from recorded triage decisions (dismissal comments on alerts,
and the issues open alerts were promoted to) rather than authored by hand
(`design.md - Decision 5`). Do not edit it; re-run the export.

All 7 findings now have a verdict, and all 7 carry `verdict_author: model` — the
remaining 6 (issues #56-#61) were triaged by the agent rather than a human, at the
repo owner's instruction, for speed rather than as a re-attempt at independence.
The scorer excludes every entry on provenance, same as before, so this completes
the tracker (every eligible finding has a verdict and an issue) without producing
an agreement figure. See `docs/security/iac-triage-measurement.md` for why no
figure exists and where measurement resumes: the 5 below-threshold first-party
findings, which the agent has not been shown.
