# IaC triage: measurement status

Date: 2026-09-03

This is the measurement record for the IaC triage pipeline
(`security/iac-security-triage/`). It exists to answer one question — *how well does the
agent triage findings in this repository?* — and today the honest answer is that the
question has not been asked yet, for a reason worth recording rather than a gap worth
quietly filling later.

## There is no agreement figure for the original corpus

The seven triage-eligible findings — the first-party ones at `HIGH` or above — were
released to the agent without an independent human verdict. All seven are now triaged, but
by the agent rather than by a human (the last six filed 2026-09-03, at the repo owner's
instruction, for speed rather than as a renewed attempt at independence). They remain
forfeited as an evaluation corpus for exactly the reason they were forfeited when only one
was triaged: the verdicts are not independent of what they would be scored against.

Running `score.py` against them would not produce a low figure; it would produce an empty
one. Only entries whose `verdict_author` is `human` contribute to agreement, and all seven
verdicts recorded for this corpus were written by a model. The scorer excluding every entry
and reporting nothing is the correct outcome, and it is preferable to a number.

The seven findings given up:

```
  5  bootstrap state bucket   AWS-0086/0087/0091/0093/0132   (n=1 each)
  2  public subnets           AWS-0164 x2                    (n=2)
```

| finding key | alert | issue | verdict |
|---|---|---|---|
| `AWS-0086:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | #1 | #48 | real-mechanical (model) |
| `AWS-0087:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | #2 | #56 | real-mechanical (model) |
| `AWS-0091:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | #4 | #57 | real-mechanical (model) |
| `AWS-0093:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | #5 | #58 | real-mechanical (model) |
| `AWS-0132:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | #7 | #59 | real-judgment (model) |
| `AWS-0164:module.vpc:aws_subnet.public_zone_1` | #8 | #60 | real-mechanical (model) |
| `AWS-0164:module.vpc:aws_subnet.public_zone_2` | #9 | #61 | real-mechanical (model) |

Per-rule agreement, stated with the support behind each figure as every figure in this
pipeline must be:

| rule | findings | agreement |
|---|---|---|
| `AWS-0086` | 1 | not measured — corpus forfeited |
| `AWS-0087` | 1 | not measured — corpus forfeited |
| `AWS-0091` | 1 | not measured — corpus forfeited |
| `AWS-0093` | 1 | not measured — corpus forfeited |
| `AWS-0132` | 1 | not measured — corpus forfeited |
| `AWS-0164` | 2 | not measured — corpus forfeited |

"Not measured" and "measured and disagreed" are different claims, and no reader of a
future report should have to guess which one an absent number meant.

## Why the forfeit is one-way

Not psychology — structure. For an *open* alert the promoted issue **is** the verdict
store: GitHub's code scanning API accepts a comment only alongside a dismissal, so
`export_fixture.py` reads an open finding's verdict out of the issue the alert was promoted
to. Every one of the seven issues now carries the agent's answer under `verdict_author:
model`. There is no second slot. Recording a human verdict for any of them means overwriting,
in the same field of the same issue, the output it was to be scored against.

`evidence` is contaminated harder still. It exists so the with/without-context comparison
can ask whether the agent reached a verdict *for the same reason* a human did — and a human
triaging these findings now would cite the ADRs after reading the agent cite them.

`export_fixture.py --allow-after-triage` exists for re-exporting a widened corpus, not for
retrofitting ground truth onto these seven.

## What it cost: a mechanism check, not an accuracy figure

No rule in this corpus exceeds n=2, and autonomous dismissal requires a support floor of 5
(`docs/adr/0007-autonomous-alert-dismissal-is-earned-per-rule.md`). The allowlist could
therefore never have opened on this corpus whatever the agreement rate came out at. What
was forfeited is the demonstration that the measurement loop closes end to end — worth
having, and recoverable — rather than any claim about how good the triage is.

## Caveats that outlive this corpus

They are not consequences of the forfeit; they were true of these seven findings from the
start and will constrain any figure computed over a corpus this shape:

- The corpus is **7 findings over 6 rules**.
- **Five of the six rules fire exactly once.** "100% agreement on `AWS-0132`" would mean
  one finding agreed.
- It reduces to roughly **two distinct judgment calls** — S3 posture on the Terraform state
  bucket, and public subnets — not seven.
- The severity gate is what narrowed it to two, **removing the two most independent
  judgments of the original four**: `AWS-0090` on the ssm scratch bucket and `AWS-0178` on
  VPC flow logs, both `MEDIUM`. That is a real cost of the gate, recorded rather than
  absorbed.

## Where measurement resumes

At the below-threshold first-party findings, which are the only ones left that the agent has
not been shown:

| finding key | severity | alert |
|---|---|---|
| `AWS-0090:module.ssm_scratch:aws_s3_bucket.this` | MEDIUM | #16 |
| `AWS-0178:module.vpc:aws_vpc.main` | MEDIUM | #10 |
| `AWS-0089:module.ssm_scratch:aws_s3_bucket.this` | LOW | #15 |
| `AWS-0094:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | LOW | #6 |
| `AWS-0089:module.bootstrap:aws_s3_bucket.terraform_state_bucket` | LOW | #3 |

Lowering `severity_threshold` in `config.json` admits them. The ordering constraint was
spent once for the original seven and is not weakened by that: **these are triaged and
exported before the next triage run, not after.** The two `MEDIUM` findings are the most
independent judgments in the original set, which is what makes the resumed corpus worth
more than its size suggests.

The corpus widens again when `live/gitlab/` lands and contributes RDS, ElastiCache and load
balancer findings. The context-delta and multi-model comparisons wait for that: over
roughly two distinct judgment calls neither delta is separable from noise.

The scorer, its disagreement test, and every caveat above are unaffected by the forfeit and
apply the moment a clean corpus exists.
