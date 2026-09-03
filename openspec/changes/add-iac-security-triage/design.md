## Context

See `proposal.md - Why` for motivation. The design-relevant facts come from an actual
Trivy run over this repo (`trivy config --format json .`), not from estimates:

- **20 findings total**, across 11 rule IDs. `AWS-0104` (unrestricted egress) accounts
  for 8 of them.
- **Severity splits almost perfectly along the ownership line.** All 8 `CRITICAL`
  findings are vendored `AWS-0104`; not one first-party finding is `CRITICAL`. The twelve
  first-party findings are 7 `HIGH`, 2 `MEDIUM`, 3 `LOW`:

  ```
    HIGH      AWS-0086 AWS-0087 AWS-0091 AWS-0093 AWS-0132   bootstrap state bucket
              AWS-0164 x2                                    modules/vpc public subnets
    MEDIUM    AWS-0090  ssm scratch bucket
              AWS-0178  VPC flow logs
    LOW       AWS-0089 x2  (bootstrap + ssm buckets)
              AWS-0094     bootstrap bucket
  ```

  A `HIGH`-and-above gate therefore leaves **7 triage-eligible findings across 6 rules**.
- **8 of 20 (40%) are in vendored registry modules** — `terraform-aws-modules/ec2-instance`
  and `terraform-aws-modules/security-group`, resolved under `.terraform/modules/`.
  Passing `--skip-dirs '**/.terraform'` does *not* exclude them; Trivy resolves and scans
  module sources regardless.
- **Trivy emits no `partialFingerprints`** in its SARIF. Finding identity must be
  constructed by us.
- **`CauseMetadata.Resource` is the module address** (`module.next_cloud`), not the
  Terraform resource address. The resource address is only recoverable from
  `CauseMetadata.Code.Lines[0].Content`.
- **`ruleId + file + startLine` is not unique**, but every collision is vendored. The
  eight `AWS-0104` findings are four pairs of sibling egress rules on adjacent lines
  (811/812 and 533/534) that no rule-plus-resource key can separate — and **all eight lie
  under `.terraform/modules/`**, so none of them is ever triaged or carries a verdict.
  Across the twelve first-party findings, rule plus module plus resource is unique.
- Trivy warns `Variable values were not found in the environment or variable files` for
  `var.domain`, so static evaluation is genuinely partial.
- `live/gitlab/` contains no `.tf` files; it is design-only and contributes nothing.

The repo is public, and `GET /repos/:owner/:repo/code-scanning/alerts` returns
`no analysis found` rather than a licensing error — third-party SARIF upload and alert
state management are available at no cost.

Two existing documents constrain the design: `docs/agents/triage-labels.md` fixes the
triage vocabulary, and `docs/agents/issue-tracker.md` fixes GitHub Issues as the sink and
`gh` as the interface.

## Goals / Non-Goals

**Goals:**

- A pipeline whose expensive stage (inference) sees only findings that could plausibly be
  acted on.
- Finding identity stable enough that unrelated edits do not re-open settled triage.
- Every verdict carries a recorded rationale, retrievable later, rather than a silent
  suppression.
- Agent output that can be *scored*, not just read.
- No component that cannot be reproduced outside this repo. The reference value depends
  on it.

**Non-Goals:**

- Being a general-purpose security platform. This targets Terraform in this repo.
- Full autonomy. The design deliberately caps what the agent may do unsupervised.
- Zero false negatives. A pipeline that dismisses nothing has no value; the design
  manages that risk rather than eliminating it.

## Decisions

### 1. Trivy alone, not Trivy + Checkov

Two scanners with overlapping AWS rulesets produce near-duplicate findings under
different IDs, which forces a cross-tool equivalence mapping — a hand-maintained table
that silently rots. With one scanner, deduplication reduces to intra-tool identity,
which is tractable (Decision 3).

*Alternative considered:* both scanners, deduplicating on resource address plus a
normalised rule category. Rejected because it would couple the evaluation's credibility to the
quality of a hand-maintained mapping table rather than to the agent. Note that corpus
size is *not* a reason to reject it — the corpus being narrow is this design's main
weakness (Decision 5), and a second scanner is one of the few cheap ways to widen it. Adding Checkov later is not blocked by anything here.

### 2. Two deterministic filters before inference: ownership, then severity

Findings are partitioned by the path of `CauseMetadata.Occurrences[0].Filename`, and what
survives is gated on `Severity`:

```
  trivy config --format json
            |
            v
  +---------------------+
  | partition by path   |
  +---------------------+
     |               |
  live/ modules/   .terraform/modules/
  FIRST-PARTY      VENDORED
  (12)             (8) -> recorded as upstream,
     |                    never sent to a model
     v
  +---------------------+
  | gate on severity    |   threshold: HIGH
  +---------------------+
     |               |
  >= HIGH          < HIGH
  ELIGIBLE (7)     (5) -> published as open alerts,
     |                    left untriaged, no issue
     v
  agent triage
```

Vendored findings are real but not actionable here: the fix belongs upstream, and the
only local remedies are pinning a different version or replacing the module — decisions
that belong to a human, not to a per-finding triage loop.

Neither of these is a judgment, so a model should not make either. Together they remove
13 of 20 findings — 65% of inference cost and 65% of the opportunity for the model to be
wrong.

**The order is load-bearing and the two filters are not substitutes.** Every `CRITICAL`
finding in this corpus is vendored (§ Context), so severity applied first or alone would
admit exactly the eight findings that can never be actioned here while excluding five
first-party ones. Ownership answers "can this repository fix it"; severity answers "is it
worth the reasoning". Only the intersection reaches the model.

The threshold is `HIGH`, recorded as configuration rather than compiled into the
partition, so raising or lowering it is a reviewable diff. Below-threshold findings are
not dismissed — dismissal is a verdict, and no verdict has been formed. They stay open in
code scanning, visible and re-triageable if the threshold moves.

*Alternative considered:* letting the agent classify ownership. Rejected — it converts a
reliable path check into a probabilistic one, and 8 of 20 findings is too large a share
to expose to that.

*Alternative considered:* passing severity to the agent as context rather than gating on
it, so the agent can weigh a `LOW` finding it judges locally serious. Rejected for now:
it restores the full inference cost to buy a judgment the agent has never been scored on,
and the five excluded findings remain visible as alerts for a human to escalate by hand.
The trade-off is recorded honestly under Risks.

### 3. Finding identity: a readable composite key

```
  key = ruleId + ":" + module_address + ":" + resource_type.resource_name
```

`module_address` comes from `CauseMetadata.Resource`; `resource_type.resource_name` is
parsed from the first cause line. The key survives line-number drift, which is the common
case (a resource gains an attribute, everything below shifts), and it is unique across
all twelve first-party findings.

It is deliberately not a hash. The key appears in the committed ground-truth fixture and
in issue bodies, where `AWS-0086:module.bootstrap:aws_s3_bucket.terraform_state_bucket`
carries more than sixty-four hex characters do. It also makes the corpus's narrowness
legible at a glance: seven of the twelve first-party keys name the same bucket, and five
of the seven eligible ones do.

*Alternatives considered:*

- *SARIF `partialFingerprints`* — not emitted by Trivy.
- *`ruleId + file + line`* — line numbers are the least stable field available.
- *Content hash of the cause lines* — changes whenever the resource is edited, including
  by the very remediation the triage recommended.
- *A `sha256` over the key plus a sibling-disambiguating ordinal* — this design's previous
  choice, now retired. The ordinal existed solely because rule-plus-resource cannot
  separate two sibling egress rules on adjacent lines. Every such collision in the corpus
  is one of the eight `AWS-0104` findings, and all eight are vendored (§ Context), so the
  ordinal disambiguated only findings that never receive a verdict — while introducing a
  failure mode in which reordering siblings permutes ordinals and silently mis-attributes
  verdicts between them. Dropping it removes that failure mode rather than documenting it.

**A guard replaces the ordinal.** Two *first-party* findings sharing a key would apply one
verdict to two distinct judgments. The normaliser reports any such collision as
`duplicate_first_party_keys` rather than absorbing it silently; the set is empty on the
current corpus and a test holds it that way.

### 4. Code scanning holds state; Issues hold work

```
      trivy SARIF (all 20 findings, first-party + vendored)
                    |
                    v
        +-------------------------+
        |  GitHub code scanning   |  durable per-finding state,
        |                         |  PR annotations, free (public)
        +-------------------------+
          |          |           |
      vendored   below       ELIGIBLE (7)
        (8)      threshold        |
         |          (5)           v
      recorded   left        +--------------------------+
      upstream   open        | GitHub Issue per finding |
                             | needs-triage + verdict   |
                             +--------------------------+
                                        |
                                  human relabels
                                        |
                    ready-for-agent / ready-for-human / wontfix
```

| Verdict the agent records | Code scanning | Issue filed | Label the agent applies |
|---|---|---|---|
| Not applicable / accepted risk | open (see § 6) | yes | `needs-triage` |
| Real, mechanical fix | open | yes | `needs-triage` |
| Real, needs judgment | open | yes | `needs-triage` |
| Cannot determine | open | yes | `needs-triage` |
| Upstream (vendored) | dismissed with rationale | no | — |
| Below severity threshold | open, untriaged | no | — |

Rationale: the two sinks answer different questions. Code scanning answers "what is the
current state of finding X" and already implements dismissal-with-reason, alert
persistence across runs, and PR annotation — none of which is worth rebuilding. Issues
answer "what work is outstanding", which is what the existing label vocabulary in
`docs/agents/triage-labels.md` was written for.

**One issue per triaged finding, not per actionable finding.** An earlier version of this
decision filed only for actionable verdicts, on the grounds that filing per finding would
flood the tracker with twenty items most of which resolve to "no". Two things changed
that. Volume: the ownership and severity filters (Decision 2) reduce twenty candidates to
seven, which is a reviewable queue rather than a flood. And purpose: deciding that a
finding is *not* worth acting on is itself the judgment this pipeline exists to inform,
and burying it in a dismissal comment on an alert hides it from the place work is
actually reviewed. A `wontfix` issue closed by a human with the agent's reasoning visible
is a better artefact than a silently dismissed alert.

**The agent proposes a verdict; a human assigns the disposition.** Every issue is filed
under `needs-triage` with the verdict and rationale in the body. A human converts it to
`ready-for-agent`, `ready-for-human` or `wontfix`. The agent never applies
`ready-for-agent` itself: that label means "fully specified, ready for an AFK agent" and
is the trigger for unattended remediation, so an agent able to apply it would be
authorising its own downstream work with no human between the finding and the change.
This boundary is the same one Decision 6 draws for alert dismissal, applied to the
tracker — and it is what makes remediation safe to build as a separate change without
revisiting anything here.

Dismissal in code scanning is therefore not the default route for a "not applicable"
verdict. It happens only where Decision 6's ratchet has earned it for that rule; until
then the verdict lives on the issue and the alert stays open.

*Alternative considered:* a committed sidecar verdict file as the source of truth.
Rejected as the primary store — it duplicates state code scanning already keeps, and
diverges from it. The evaluation fixture (Decision 5) is not an exception to this: it is
*derived from* alert state by export, never authored alongside it, so there is exactly one
place a verdict is recorded and the fixture is a snapshot of it.

### 5. Ground truth is harvested from real triage, not authored beside it

The seven triage-eligible findings are triaged **in code scanning** — dismiss-with-comment,
or left open and promoted to an issue — and the ground-truth fixture is then exported from
alert state via `gh api`:

```
  trivy -> SARIF -> code scanning -> [human triages the 7 eligible alerts]
                                              |
                                     gh api .../code-scanning/alerts
                                              |
                                     join to normalised records by key
                                              |
                                     fixtures/ground-truth.yaml
```

The corpus covers exactly the set the agent triages. The five below-threshold first-party
findings carry no human verdict: labelling them would build a corpus the scorer can never
use, and would invite the mistake of scoring the agent on findings it was never shown.
Should the threshold drop, they are triaged and exported then — the export is a repeatable
operation, not a one-off.

This is the same labelling work either way; the difference is that it happens in the tool
that holds the state, produces alert history as its audit trail, and leaves the repository
better off whether or not the agent ever ships. A hand-filled worksheet would be a second
verdict store standing next to the real one — exactly what Decision 4 rejects.

The ordering constraint is unchanged and non-negotiable: triage is performed and exported
**before** any triage run exists. Verdicts formed with knowledge of agent output cannot
support an agreement figure. Alert timestamps make the ordering auditable, which a
hand-edited file could not.

**Spent once, deliberately (2026-09-03).** The original seven eligible findings were
released to the agent without an independent human verdict, forfeiting them as a corpus.
The reasoning is recorded under task 3.1: what was given up is a mechanism check rather
than an accuracy figure, since no rule in that set exceeds n=2 against Decision 6's
support floor of 5, so the allowlist could never have opened on it whatever the agreement
rate. The forfeit is one-way for a structural reason, not merely a psychological one —
for an open alert the promoted issue *is* the verdict store, so once an issue carries the
agent's verdict there is no second slot a human verdict could occupy without overwriting
the output it would be scored against.

The constraint itself is not relaxed by having been spent. It binds the next corpus: the
below-threshold findings admitted by a threshold drop, which are the only findings left
that the agent has not been shown.

Each fixture entry carries the verdict, a written rationale, and `evidence` — the ADRs and
design docs relied on, parsed from the dismissal comment. `evidence` exists so that
Decision 7's comparison can ask whether the agent reached a verdict *for the same reason*
a human did, not merely whether it landed on the same answer; with a corpus this small
that distinction carries more signal than the agreement rate.

**What this corpus can and cannot support.** The severity gate makes an already narrow
corpus narrower. Of the seven eligible findings, five concern S3 posture on the Terraform
state bucket and two concern public subnets:

```
  5  bootstrap state bucket   AWS-0086/0087/0091/0093/0132   (n=1 each)
  2  public subnets           AWS-0164 x2                    (n=2)
```

There are roughly **two distinct judgment calls** here, not seven — down from four before
the gate, because the two `MEDIUM` findings the gate excludes (`AWS-0090` on the ssm
scratch bucket, `AWS-0178` on VPC flow logs) were the two most independent judgments in
the set. This is a real cost of the gate, not a rounding error, and it is recorded under
Risks rather than absorbed.

Worse for measurement, **five of the six eligible rules fire exactly once**, so "100%
agreement on `AWS-0132`" means one finding agreed. `AWS-0164` at n=2 is the largest rule
in the corpus. This is adequate to validate the *mechanism* and inadequate to support any
accuracy claim, and it is the direct reason autonomy needs a minimum-support floor rather
than an agreement threshold alone (Decision 6).

A previously planned `difficulty` field is dropped. Its only consumer was a stratified
breakdown of Decision 7's comparison, which is deferred until the corpus is wide enough
for a stratified result to be distinguishable from noise. A self-assessed difficulty from
a single rater who also wrote the ADRs the agent reads was never going to carry that
weight.

The corpus becomes genuinely interesting once `live/gitlab/` exists and contributes RDS,
ElastiCache and load balancer findings.

### 6. Autonomy as a ratchet, gated on agreement *and* support

```
  phase 1: PROPOSE            phase 2: DISMISS (scoped)      phase 3: DISMISS (broad)
  agent writes verdicts       auto-dismiss only for rule      allowlist widened as
  to a PR comment;            IDs with full agreement         evidence accumulates
  human applies them          over >= 5 scored findings;
                              others still proposed
```

The agent starts with no write authority over alert state. Authority is granted per rule
ID, and only where the evidence for that rule is both **unanimous and large enough to
mean something**.

The support floor is the load-bearing half. Full agreement alone is not a bar: five of
the six eligible rules fire exactly once (Decision 5), so an agreement-only gate would
hand a rule permanent unsupervised dismissal authority on the strength of a single case
going the right way. Five sixths of the eligible ruleset could be unlocked by coin flips
landing well. `k = 5` is a judgment, not a derivation — it is small enough to be reachable
and large enough that unanimity is not cheap.

**On today's corpus no rule clears the floor** (the largest, `AWS-0164`, is n=2), so the
allowlist is empty and phase 2 is unreachable until the corpus widens. That is the correct
outcome, and a better claim than an auto-dismissal justified by n=1.

This is also why the routing in Decision 4 does not dismiss on a "not applicable" verdict:
with no rule allowlisted, every such verdict travels to a human as an issue, and the alert
stays open behind it.

Rationale: a triage agent that wrongly dismisses a real finding is worse than no scanner,
because it manufactures confidence. Autonomy is therefore treated as something earned
against evidence rather than configured. The ratchet is also the most transferable part of
this design — "we let a model triage" is not a case anyone can take to a security review;
"here is per-rule agreement, here is the support behind each figure, and here is the policy
gating autonomy on both" is.

### 7. ADRs and design docs are agent context

`docs/adr/` and `docs/design/` are supplied to the triage agent alongside each finding.

This is the pipeline's actual differentiator over a suppression file. A rule engine
cannot know that a permissive egress rule is intentional per `ADR-0004`; a model with the
ADR in context can. The evaluation should measure this directly by running the same
corpus with and without doc context — a null result is itself a useful finding, since it
would say the value is in the model rather than in the repo's documentation discipline
(and would weaken the case for transferring this to teams without ADRs).

**Deferred until the corpus widens.** Over two distinct judgment calls — the severity gate
having removed the two most independent of the four (Decision 5) — the difference between
a with-context and a without-context run is not separable from noise, and reporting it
would be the same overclaim the support floor exists to prevent. The
`evidence` field is still captured now, so the comparison is runnable the moment the
corpus can carry it.

### 8. Static HCL now; plan-JSON deferred

Scanning `terraform show -json` resolves variables and module composition and would
eliminate the `var.domain` warning above, at the cost of AWS credentials in CI and a
successful `terraform plan`.

Deferred, for a reason specific to this repo rather than a general preference: `modules/`
is not independently plannable and `live/gitlab/` has no Terraform at all, so plan-based
scanning would cover strictly less of the codebase than static analysis does. It also
makes the fixture corpus depend on live AWS state, which undermines its use as a
regression test. Static scanning runs on fork PRs with no secrets and is fully
reproducible.

The OIDC role needed for plan-JSON is available (confirmed with the repo owner) and is
not blocked — this is a sequencing decision, revisitable once `live/gitlab/` exists.

### 9. Terraform only; Ansible, shell and `user_data` deferred

An LLM auditor is the *only* option for `user_data_*.sh` and the Ansible roles, since no
deterministic scanner covers them well. That makes them the most interesting target and
the wrong place to start — though not for the reason of ground truth being unavailable:
Terraform's ground truth is hand-assigned too (Decision 5), and the same hand could label
shell findings. The real reason is sequencing. Terraform findings come with a scanner
baseline, so the agent's verdicts can be compared against something it did not itself
produce; on `user_data` the agent would be both the finder and the judge, and a
disagreement rate would have no denominator. Phase 2, once false-dismissal behaviour on
Terraform is characterised.

### 10. seclab-taskflow-agent, using its generic half only

The framework splits cleanly into a generic engine (personalities, taskflows, toolboxes,
checkpointing, multi-model comparison) and CodeQL-oriented security content. Only the
engine is used; CodeQL supports neither HCL nor Ansible and is irrelevant here.

The engine supplies exactly the primitives this pipeline needs, so the whole pipeline is
one declarative file rather than bespoke glue:

```
  task 1   run:      trivy config --format json
                     | normalise + key + partition + severity gate
           outputs:  {eligible: [...], below_threshold: [...], vendored: [...]}
                        |                          <- JSON Schema validated
  task 2   over:     outputs.eligible
           agents:   [iac_triage_agent]  + ADR/design context
           outputs:  {verdict, confidence, rationale}
                        |
  task 3   run:      gh issue create (one per verdict, needs-triage)
```

Invoked by hand rather than by a trigger (Decision 11), which is the shape the CLI already
has.

`run:` (shell tasks), `outputs:` (schema-validated structured objects) and `over:`
(fan-out) are demonstrated in `examples/taskflows/example_typed_outputs.yaml`.

*Alternative considered:* a skill driven by Claude Code, already configured in this repo
and requiring no new dependency. Rejected for this change specifically because the goal
includes producing a reproducible, unattended, auditable pipeline whose definition can be
reviewed as an artefact — which is what the YAML buys. For interactive one-off triage the
skill would be the better tool.

### 11. Scanning is automatic; triage is invoked on demand

The Trivy scan and SARIF upload run on every pull request and on `main`. Triage runs only
when a human dispatches it — a second workflow with `workflow_dispatch` as its sole
trigger, calling the taskflow CLI.

Three reasons, in order of weight:

- **It matches what the framework is.** `seclab-taskflow-agent` is a CLI with no event
  model, no webhook listener and no Actions integration; every documented entry point is
  an explicit invocation. Driving it from a push trigger would mean wrapping a
  batch-oriented tool in an event-oriented harness for no gain.
- **Triage is a batch judgment over a corpus, not a per-commit check.** A push changes at
  most a couple of findings, but a triage run reads ADRs and design docs and files issues;
  running it per push would re-file the same seven issues' worth of reasoning against a
  corpus that barely moved.
- **Cost and blast radius are bounded by a human decision.** Inference spend and issue
  creation both happen only when someone asks for them, and `AI_API_TOKEN` is never
  reachable from a fork PR because no fork-triggerable workflow references it.

The two-workflow split is what makes the degradation requirement trivially true rather
than carefully engineered: the scan workflow has no dependency on the triage workflow, so
if triage cannot run, findings are published anyway.

This closes what was previously an open question ("per-PR or scheduled"). A scheduled run
remains available later as a convenience — it is the same invocation on a timer — but it
is not this change's default, because a schedule reintroduces unattended issue creation
without adding a judgment.

*Alternative considered:* triage on every push to `main`. Rejected on the second and third
reasons above; the first would not have blocked it.

## Risks / Trade-offs

- **Agent dismisses a genuine finding** → Phase 1 grants no dismissal authority at all;
  phase 2 grants it per rule ID only where fixture agreement is 100%. Dismissals stay
  visible and reversible in code scanning rather than being deleted.
- **Fixture corpus too small to generalise (20 findings, 8 of one rule; 8 of 10
  first-party rules fire once)** → Treated as mechanism validation, not an accuracy claim.
  Structurally contained by the minimum-support floor (Decision 6), which makes the
  allowlist empty rather than trusting a caveat to be read; Decision 5 additionally
  requires the support behind every reported figure to be stated alongside it.
- **Two first-party findings share a key and so share a verdict** → Cannot occur on the
  current corpus, and is reported rather than absorbed if a future scan produces it
  (Decision 3). This replaces the ordinal scheme, whose own failure mode — sibling
  reordering silently mis-attributing verdicts — is now gone rather than accepted.
- **The severity gate is a deliberate false-negative surface** → Five first-party
  findings, including the two most independent judgment calls in the corpus (`AWS-0090`,
  `AWS-0178`), are never reasoned about. Trivy's severity is a property of the rule, not
  of this system, so a `MEDIUM` finding here could matter more than a `HIGH` one. Contained
  by keeping those alerts open and visible rather than dismissed, by recording the
  threshold as reviewable configuration, and by the export being repeatable if the
  threshold drops — but not eliminated, and it narrows the measurable corpus from four
  distinct judgments to two (Decision 5).
- **An issue per finding makes the tracker noisier** → Seven issues per full run rather
  than the two or three an actionable-only filter would produce, deduplicated on finding
  key across runs (Decision 4). Accepted: the filters keep the number small, and a
  `wontfix` decision recorded in the tracker is worth more than a dismissal buried in
  alert state.
- **Static scanning misses variable-dependent misconfigurations** → Known and observable
  today (`var.domain`); the plan-JSON path stays open (Decision 8).
- **Triage quality depends on ADR quality** → Made explicit and measurable by the
  with/without-context comparison (Decision 7) rather than assumed.
- **New dependency on a young, single-org framework** → Confined to orchestration.
  Scanner, sinks and fixtures are framework-independent, so replacing the engine would
  not invalidate the corpus or the routing design.
- **Inference cost and CI latency** → 65% cut deterministically before inference, and
  triage does not run on PRs at all (Decision 11), so no pull request waits on a model.
- **`AI_API_TOKEN` in a public repo** → Repository secret, and no fork-triggerable workflow
  references it: the scan workflow needs no secret and the triage workflow is
  `workflow_dispatch`-only, so a fork PR cannot reach it.
- **A human forgets to invoke triage** → On-demand invocation trades timeliness for
  control. Findings accumulate as untriaged alerts in the meantime, which is visible, and
  a schedule can be added later (Decision 11) without changing anything else.

## Migration Plan

There is no existing behaviour to migrate. Deployment is ordered so each stage is useful
alone and the next is only reached if the previous holds:

1. Trivy in CI, SARIF uploaded to code scanning. Independently valuable; no agent, no
   secrets, no AWS access.
2. Normalisation, finding keys, the ownership partition and the severity gate, verified
   against the current corpus.
3. The seven eligible alerts triaged in code scanning; fixtures exported from
   alert state and committed, before any triage run exists.
4. Triage taskflow in propose-only mode, dispatched by hand, scored against fixtures.
5. Issue routing: one issue per triaged finding under `needs-triage`.
6. Scoped dismissal authority for rules that met the bar in step 4.

**Rollback:** each stage is additive and independently revertible. Removing the triage
workflow leaves the Trivy scan intact; removing everything leaves the repo as it was,
since no scanner output is load-bearing for any other process.

## Open Questions

- Whether an on-demand run should later be supplemented by a schedule. Decision 11 settles
  the default (dispatch only); a timer is additive and changes no other decision.
- Whether `HIGH` is the right threshold, or whether `MEDIUM` is the better gate given that
  the two excluded `MEDIUM` findings are the corpus's most independent judgments
  (Decision 5). Answerable once agreement on the `HIGH` set is measured.
- Whether the fixture set is re-exported or hand-merged when Trivy's ruleset introduces
  new rules. Answerable the first time it happens.
- Whether `k = 5` is the right support floor. It is a judgment (Decision 6) and should be
  revisited once any rule actually approaches it.
- Which specific dismissal reason code best represents "upstream, vendored module" in the
  code scanning API. A presentation detail within Decision 4.
