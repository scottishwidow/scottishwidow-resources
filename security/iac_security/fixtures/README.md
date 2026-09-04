# Fixtures

`baseline-scan.json` is the raw output of `trivy config --format json .` run against
the repository at the point this capability was introduced (main@06680c9). It is the
corpus referenced throughout `openspec/changes/add-iac-security-triage/design.md` and
`specs/iac-security-triage/spec.md`: 20 findings across 11 rule IDs.

It is a fixture, not a live artifact — regenerate deliberately (`trivy config --format
json .` from the repo root) rather than overwriting it as part of routine scans.

It is what the test suites scan instead of Trivy: every test that exercises
`normalise.py`, the taskflow's fan-out over eligible findings, or `file_issues.py`
replays this report rather than running a live scan, so the suites need neither
Trivy nor AWS.
