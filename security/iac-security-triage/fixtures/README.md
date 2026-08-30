# Fixtures

`baseline-scan.json` is the raw output of `trivy config --format json .` run against
the repository at the point this capability was introduced (main@06680c9). It is the
corpus referenced throughout `openspec/changes/add-iac-security-triage/design.md` and
`specs/iac-security-triage/spec.md`: 20 findings across 11 rule IDs.

It is a fixture, not a live artifact — regenerate deliberately (`trivy config --format
json .` from the repo root) rather than overwriting it as part of routine scans.

`ground-truth.yaml` will hold the human verdicts for the 12 first-party findings,
exported from GitHub code scanning alert state rather than authored by hand
(`design.md - Decision 5`). It does not exist yet; it is created by task 3.2 once
the alerts have been triaged.
