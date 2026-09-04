# IaC security triage

Tooling for the `iac-security-triage` capability
(`openspec/specs/iac-security-triage/spec.md`). Everything in this directory is
stdlib Python: no framework, no network, no cloud credentials.

`taskflow/` is the exception and the boundary is deliberate. It holds the only
part that needs `seclab-taskflow-agent`, Docker and a model token, so replacing
the orchestration engine would touch that directory and nothing else — the
scanner, the identity scheme and the fixture do not know it exists
(`design.md - Decision 10`).

## Pipeline

```
trivy config --format json .
        |
        v
normalise.py   one record per finding, keyed, then filtered twice:
        |      ownership by path, then severity against the threshold
        |      -> {"eligible": [...], "below_threshold": [...], "vendored": [...]}
        v
taskflow/   one verdict per eligible finding, with a rationale
        |   -- see taskflow/README.md
        v
file_issues.py   one GitHub issue per triaged finding, under needs-triage,
                 idempotent on the finding key
```

The pipeline routes and reasons; it does not claim to be measurably right.
There is no scorer and no ground-truth fixture, because every verdict this
corpus has ever carried was written by the agent, not a human, and a verdict
cannot score the model that wrote it.

    trivy config --format json . \
      | python3 security/iac_security/normalise.py

`normalise.py` accepts a report path instead of stdin, so the committed baseline
can be replayed without a scanner:

    python3 security/iac_security/normalise.py \
      security/iac_security/fixtures/baseline-scan.json

## The two filters

Ownership runs first, severity second, and neither is a judgment
(`design.md - Decision 2`). On the baseline corpus, at the `MEDIUM` threshold
configured today:

| | count | what happens to it |
|---|---|---|
| `eligible` | 9 | sent for triage |
| `below_threshold` | 3 | stays an open alert, untriaged, no issue |
| `vendored` | 8 | recorded upstream, never sent to a model |

At the `HIGH` threshold this started on, the same corpus splits 7 / 5 / 8. The
move from one to the other is the whole of the change: no key changed and no
recorded verdict was disturbed.

The order is load-bearing. All eight `CRITICAL` findings in this repo are
vendored, so a severity gate applied alone would admit exactly the eight
findings that cannot be fixed here and drop five first-party ones.

The threshold lives in `config.json`, not in the partition logic, so moving it
is a reviewable diff:

    {"severity_threshold": "MEDIUM"}

Below threshold means *untriaged*, not dismissed — dismissal is a verdict and
none has been formed. Those findings keep their key, so lowering the threshold
extends what has been triaged rather than resetting it. Each record carries a
`triage_status` of `eligible`, `below-threshold` or `upstream`; nothing here
assigns a verdict from `vocabulary.py`.

## Identity and ownership

A finding's identity is the readable composite key
`ruleId:module_address:resource_type.resource_name`, per `design.md - Decision 3`
— for example:

    AWS-0089:module.bootstrap:aws_s3_bucket.terraform_state_bucket

It survives line-number drift and is unique across all 12 first-party findings.
It is not a hash because it appears in issue bodies, where it should be
readable.

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

## Routing to the tracker

Code scanning holds per-finding state; Issues hold the work (`design.md -
Decision 4`). `file_issues.py` promotes **every** triaged finding to an issue,
whatever the verdict — deciding that a finding is not worth acting on is the
judgment this pipeline exists to inform, and burying it in a dismissal comment
hides it from where work is reviewed.

    python3 security/iac_security/file_issues.py \
      --findings normalised.json --verdicts runs/<id>.json --dry-run

| | issue filed | label applied | alert |
|---|---|---|---|
| any verdict on an eligible finding | yes | `needs-triage` | left open |
| below threshold | no | — | left open, untriaged |
| vendored | no | — | recorded upstream |

Three properties, each a boundary rather than a convenience:

- **`ready-for-agent` is never applied.** That label authorises unattended
  remediation, so an agent that could apply it would be authorising its own
  downstream work. It is absent from the emittable vocabulary and a label
  outside that vocabulary raises rather than being filed.
- **No alert state is touched.** Nothing in the module speaks to the code
  scanning API, so a `not-applicable` verdict files an issue and leaves the alert
  open. Nothing merges and nothing is dismissed without a human, permanently
  (ADR-0008).
- **Only findings the pipeline submitted for triage are filed.** A verdict
  arriving for a vendored or below-threshold finding is reported as an error,
  because honouring it would defeat the gate that excluded it.

Idempotency is keyed on the finding key, read back out of existing issue bodies
by `issue_body.py` across open *and* closed issues. A second run over unchanged
verdicts creates nothing and edits nothing — the disposition label a human
applied is this pipeline's output and must survive the next run of it.

In CI this is a separate job from the one that runs the agent: the job holding
`issues: write` never sees `AI_API_TOKEN`, and the job that runs the model
cannot open an issue.

## Propose-only, permanently

Nothing here can write alert state. The pipeline's safety property is one
sentence, per ADR-0008: nothing merges and nothing is dismissed without a
human. There is no earned-autonomy ratchet — ADR-0007 proposed one, and
ADR-0008 supersedes it and puts autonomous dismissal out of scope permanently
rather than unearned.

No workflow in this repository is granted `security-events: write` for
triage, and a test asserts that per job.

## Tests

    python3 -m unittest discover -s security/iac_security/tests
    python3 -m unittest discover -s security/iac_security/taskflow/tests

They run against the committed baseline fixture, so they need neither Trivy nor
AWS — nor, for the second suite, Docker or a model token.
