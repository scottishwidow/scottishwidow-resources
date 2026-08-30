# IaC security triage

Tooling for the `iac-security-triage` capability
(`openspec/specs/iac-security-triage/spec.md`). Everything here is stdlib Python
plus PyYAML; no framework, no network, no cloud credentials.

## Pipeline

```
trivy config --format json .
        |
        v
normalise.py   one record per finding, fingerprinted, partitioned by ownership
        |      -> {"first_party": [...], "vendored": [...]}
        v
worksheet.py   one YAML entry per first-party finding, for a human to label
```

    trivy config --format json . \
      | python3 security/iac-security-triage/normalise.py \
      | python3 security/iac-security-triage/worksheet.py -o worksheet.yaml

`normalise.py` accepts a report path instead of stdin, so the committed baseline
can be replayed without a scanner:

    python3 security/iac-security-triage/normalise.py \
      security/iac-security-triage/fixtures/baseline-scan.json

## Identity and ownership

Finding identity is `sha256(rule|module_address|resource_address:ordinal)`, per
`design.md - Decision 3`. The core survives line-number drift; the ordinal
separates sibling findings — four `AWS-0104` findings in the corpus share a rule,
a file and a line, and are distinguishable only this way.

Ownership is a path check over `Occurrences[0].Filename`, never a model's
judgment (`Decision 2`): anything under `.terraform/modules/` is vendored, and
`live/` and `modules/` are first-party. An unrecognised path is treated as
first-party — so nothing escapes triage by being somewhere unexpected — and
reported on stderr and in `unrecognised_locations`.

## Tests

    python3 -m unittest discover -s security/iac-security-triage/tests

They run against the committed baseline fixture, so they need neither Trivy nor
AWS.
