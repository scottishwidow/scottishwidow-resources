# Fixtures

`baseline-scan.json` is the raw output of `trivy config --format json .` run against
the repository at the point this capability was introduced (main@06680c9). It is the
corpus referenced throughout `openspec/changes/add-iac-security-triage/design.md` and
`specs/iac-security-triage/spec.md`: 20 findings across 11 rule IDs.

It is a fixture, not a live artifact — regenerate deliberately (`trivy config --format
json .` from the repo root) rather than overwriting it as part of routine scans.

`labelling-worksheet.yaml` is generated from `baseline-scan.json` by
`normalise.py | worksheet.py` and holds the 12 first-party findings awaiting
human verdicts. Regenerate it only alongside the baseline; the human fields are
filled in by hand and are the ground truth agent output is scored against.
