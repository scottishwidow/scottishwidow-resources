# IaC security triage

Tooling for the `iac-security-triage` capability
(`openspec/specs/iac-security-triage/spec.md`). Everything in this directory is
stdlib Python: no framework, no network, no cloud credentials.

`taskflow/` is the exception and the boundary is deliberate. It holds the only
part that needs `seclab-taskflow-agent`, Docker and a model token, so replacing
the orchestration engine would touch that directory and nothing else — the
scanner, the identity scheme, the fixtures and the scoring do not know it
exists (`design.md - Decision 10`).

## Pipeline

```
trivy config --format json .
        |
        v
normalise.py   one record per finding, keyed, then filtered twice:
        |      ownership by path, then severity against the threshold
        |      -> {"eligible": [...], "below_threshold": [...], "vendored": [...]}
        v
GitHub code scanning   where findings are triaged and verdicts recorded
        |
        v
export_fixture.py   joins recorded verdicts onto the eligible findings
        |           -> fixtures/ground-truth.yaml (schema-checked)
        v
score.py   agreement per rule, each figure with the count behind it
        ^
        |
taskflow/   the agent's verdicts, for the same findings, to be scored against
        |   the fixture above -- see taskflow/README.md
        v
file_issues.py   one GitHub issue per triaged finding, under needs-triage,
        |        idempotent on the finding key
        v
autonomy.py   which alerts, if any, may be dismissed without a human
```

The two arms meet at `score.py`, and the order between them is the point: the
fixture is recorded from human triage *before* the agent runs over the same
findings, because a verdict written after seeing the agent's answer cannot
measure it. `taskflow/` is scoped to the findings whose ground truth already
exists, so the rest stay clean until they are triaged.

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
extends the ground-truth corpus rather than resetting it. Each record carries a
`triage_status` of `eligible`, `below-threshold` or `upstream`; nothing here
assigns a verdict from `vocabulary.py`.

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

There is no hand-labelling worksheet. The 7 eligible findings are triaged in
GitHub code scanning and the ground-truth fixture is exported from that state
(`design.md - Decision 5`), so verdicts live where the triage happened rather
than in a second store.

A verdict is recorded in one of two places, and `export_fixture.py` reads both:

- **A dismissed alert** carries `not-applicable` in the act itself and its
  reasoning in the dismissal comment.
- **An open alert** has nowhere to put a rationale — the code scanning API
  accepts a comment only alongside a dismissal — so its verdict lives on the
  issue the alert was promoted to, joined back by the finding key in the issue
  body. This is not the second verdict store `Decision 4` rejects: for an open
  alert it is the *first* one.

Export, then check it, then score a run against it:

    python3 security/iac_security/export_fixture.py
    python3 security/iac_security/score.py --run verdicts.json

The export refuses to run once `runs/` exists, because a fixture written after a
triage run is not independent of it. `--allow-after-triage` overrides that, and
the result is not ground truth.

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
  open. Dismissal is earned per rule under `Decision 6` and happens elsewhere.
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

## Provenance is part of the verdict

Every fixture entry carries `verdict_author`: `human`, `model`, or `unknown` for
an entry that never declared one. Only `human` entries contribute to an
agreement figure, because a verdict written by a model cannot score that model.

`score.py` therefore reports three exclusions rather than folding them into the
percentage: entries excluded on provenance, rules absent from the fixture (which
are flagged as needing a human verdict rather than counted as agreement), and
fixture entries the run never covered. Every figure it prints comes with the
number of findings behind it — eight of the ten first-party rules here fire once,
so an agreement figure without its support is a coin flip reported as a
measurement.

There is no agreement figure for the current corpus, and the reason is recorded
in `docs/security/iac-triage-measurement.md` rather than left as an absence: the
7 eligible findings were released to the agent untriaged and forfeited as an
evaluation corpus, and measurement resumes over the 5 below-threshold first-party
findings once the threshold drops.

## Autonomy is earned, per rule

`autonomy.py` is the only thing here that can write alert state, and on this
corpus it writes nothing. Dismissal requires all three of
(`design.md - Decision 6`, `docs/adr/0007-autonomous-alert-dismissal-is-earned-per-rule.md`):

    agreement == 100%   AND   scored >= support_floor   AND   rule allowlisted

    python3 security/iac_security/autonomy.py \
      --verdicts runs/<id>.json --evidence score.json     # report only
    python3 security/iac_security/autonomy.py ... --apply
    python3 security/iac_security/autonomy.py --reopen <alert>

The support floor is the load-bearing half. Five of the six eligible rules fire
exactly once, so an agreement-only gate would grant five sixths of the ruleset
permanent dismissal authority on single cases going the right way. `k = 5` is a
judgment, not a derivation, and a floor of 1 or less is refused at load rather
than accepted.

`autonomy.json` holds the floor and the allowlist. It is **empty**, and no rule
on this corpus could qualify — the largest, `AWS-0164`, is n=2. A test derives
that from the baseline rather than restating it, so it moves when the corpus
does.

The allowlist is necessary and *not* sufficient: evidence is re-checked at run
time against the scoring report, so a grant that outlives its evidence is
reported as an error instead of being honoured. The file can only narrow what
the measurement permits, never widen it.

Everything else is proposed — never scored, scored below full agreement, agreed
but under-supported, or qualifying-but-not-granted all leave the alert open and
send the verdict to a human as an issue. Dismissal itself is an edit and not a
deletion: the alert stays listed, the rationale and finding key are written onto
it, and `--reopen` reverses it.

Nothing runs this in CI. No workflow in this repository is granted
`security-events: write` for triage, and a test asserts that per job — standing
authority to close alerts is not something to hold while the allowlist is empty.
It becomes a wiring question when a rule first clears the floor, and not before.

## Tests

    python3 -m unittest discover -s security/iac_security/tests
    python3 -m unittest discover -s security/iac_security/taskflow/tests

They run against the committed baseline fixture, so they need neither Trivy nor
AWS — nor, for the second suite, Docker or a model token.
