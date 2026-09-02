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

It is incomplete: 1 of 7 findings has a verdict, and that one was written by a
model rather than a human, so it carries `verdict_author: model` and the scorer
excludes it. Until the remaining 6 are triaged by a human, no agreement figure
computed against this fixture means anything.
