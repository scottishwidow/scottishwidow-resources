# IaC security triage

Tooling for the `iac-security-triage` capability
(`openspec/specs/iac-security-triage/spec.md`). Everything here is stdlib Python;
no framework, no network, no cloud credentials.

## Pipeline

```
trivy config --format json .
        |
        v
normalise.py   one record per finding, keyed and partitioned by ownership
        |      -> {"first_party": [...], "vendored": [...]}
        v
GitHub code scanning   where findings are triaged and verdicts recorded
        |
        v
fixtures/ground-truth.yaml   exported from alert state (not yet implemented)
```

    trivy config --format json . \
      | python3 security/iac-security-triage/normalise.py

`normalise.py` accepts a report path instead of stdin, so the committed baseline
can be replayed without a scanner:

    python3 security/iac-security-triage/normalise.py \
      security/iac-security-triage/fixtures/baseline-scan.json

## Identity and ownership

A finding's identity is the readable composite key
`ruleId:module_address:resource_type.resource_name`, per `design.md - Decision 3`
— for example:

    AWS-0089:module.bootstrap:aws_s3_bucket.terraform_state_bucket

It survives line-number drift and is unique across all 12 first-party findings.
It is not a hash because it appears in the committed fixture and in issue bodies,
where it should be readable.

There is no ordinal. Rule-plus-resource cannot separate sibling egress rules on
adjacent lines, but every such collision in the corpus is one of the 8
`AWS-0104` findings and **all 8 are vendored**, so they never carry a verdict.
Two *first-party* findings sharing a key would apply one verdict to two
judgments, so that case is reported as `duplicate_first_party_keys` rather than
absorbed; it is empty on the baseline and a test holds it that way.

Ownership is a path check over `Occurrences[0].Filename`, never a model's
judgment (`Decision 2`): anything under `.terraform/modules/` is vendored, and
`live/` and `modules/` are first-party. An unrecognised path is treated as
first-party — so nothing escapes triage by being somewhere unexpected — and
reported on stderr and in `unrecognised_locations`.

## Labelling

There is no hand-labelling worksheet. The 12 first-party findings are triaged in
GitHub code scanning and the ground-truth fixture is exported from alert state
(`design.md - Decision 5`), so verdicts live in one place rather than two.

## Tests

    python3 -m unittest discover -s security/iac-security-triage/tests

They run against the committed baseline fixture, so they need neither Trivy nor
AWS.
