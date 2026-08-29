## Context

See `proposal.md - Why` for motivation. The design-relevant facts come from an actual
Trivy run over this repo (`trivy config --format json .`), not from estimates:

- **20 findings total**, across 11 rule IDs. `AWS-0104` (unrestricted egress) accounts
  for 8 of them.
- **8 of 20 (40%) are in vendored registry modules** — `terraform-aws-modules/ec2-instance`
  and `terraform-aws-modules/security-group`, resolved under `.terraform/modules/`.
  Passing `--skip-dirs '**/.terraform'` does *not* exclude them; Trivy resolves and scans
  module sources regardless.
- **Trivy emits no `partialFingerprints`** in its SARIF. Finding identity must be
  constructed by us.
- **`CauseMetadata.Resource` is the module address** (`module.next_cloud`), not the
  Terraform resource address. The resource address is only recoverable from
  `CauseMetadata.Code.Lines[0].Content`.
- **`ruleId + file + startLine` is not unique.** Four `AWS-0104` findings collide
  pairwise on every SARIF field; they are distinguishable only by the module
  instantiation that produced them (`module.next_cloud` vs `module.song_vault`), which
  SARIF does not carry.
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
normalised rule category. Rejected as disproportionate work for a 770-LOC corpus, and it
would have coupled the evaluation's credibility to the quality of a mapping table rather
than to the agent. Adding Checkov later is not blocked by anything here.

### 2. Deterministic ownership filter before inference

Findings are partitioned by the path of `CauseMetadata.Occurrences[0].Filename`:

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
     |               |
     v               v
  agent triage    recorded as upstream,
  (12 findings)   never sent to a model
                  (8 findings)
```

Vendored findings are real but not actionable here: the fix belongs upstream, and the
only local remedies are pinning a different version or replacing the module — decisions
that belong to a human, not to a per-finding triage loop.

This is a rule, not a judgment, so a model should not make it. It also removes 40% of
inference cost and 40% of the opportunity for the model to be wrong.

*Alternative considered:* letting the agent classify ownership. Rejected — it converts a
reliable path check into a probabilistic one, and 8 of 20 findings is too large a share
to expose to that.

### 3. Finding identity: stable core plus ordinal

```
  core     = ruleId + module_address + resource_type.resource_name
  ordinal  = index among findings sharing that core, ordered by start line
  id       = sha256(core + ":" + ordinal)
```

`module_address` comes from `CauseMetadata.Resource`; `resource_type.resource_name` is
parsed from the first cause line. The core survives line-number drift, which is the
common case (a resource gains an attribute, everything below shifts). The ordinal exists
only because the core genuinely cannot separate two sibling egress rules on adjacent
lines.

*Alternatives considered:*

- *SARIF `partialFingerprints`* — not emitted by Trivy.
- *`ruleId + file + line`* — demonstrably collides on this corpus (four `AWS-0104`
  findings), and line numbers are the least stable field available.
- *Content hash of the cause lines* — changes whenever the resource is edited, including
  by the very remediation the triage recommended.

**Known weakness, accepted:** reordering sibling resources within a file permutes
ordinals and mis-attributes verdicts between them. This is rare, affects only findings
sharing an identical core, and is detectable — the fixture set will catch it. Recorded
here rather than engineered around, because the alternatives are worse.

### 4. Code scanning holds state; Issues hold work

```
      trivy SARIF (all findings, first-party + vendored)
                    |
                    v
        +-------------------------+
        |  GitHub code scanning   |  durable per-finding state,
        |                         |  PR annotations, free (public)
        +-------------------------+
              |             |
         dismissed       promoted
         + rationale         |
                             v
                    +----------------+
                    | GitHub Issues  |  actionable work only
                    | + triage label |
                    +----------------+
```

| Verdict | Code scanning | Issue |
|---|---|---|
| Not applicable / accepted risk | dismissed, rationale in comment | none |
| Upstream (vendored) | dismissed as `used in tests`-equivalent with rationale | none |
| Real, mechanical fix | open | `ready-for-agent` |
| Real, needs judgment | open | `ready-for-human` |
| Cannot determine | open | `needs-info` |

Rationale: the two sinks answer different questions. Code scanning answers "what is the
current state of finding X" and already implements dismissal-with-reason, alert
persistence across runs, and PR annotation — none of which is worth rebuilding. Issues
answer "what work is outstanding", which is what the existing label vocabulary in
`docs/agents/triage-labels.md` was written for. Filing an issue per finding would flood
the tracker with 20 items, most of which resolve to "no".

*Alternative considered:* a committed sidecar verdict file as the source of truth.
Rejected as the primary store — it duplicates state code scanning already keeps, and
diverges from it. It survives in reduced form as the fixture set (Decision 5), which is
ground truth for *evaluation*, not for runtime state.

### 5. Ground truth before autonomy

All 20 current findings are hand-labelled once by a human and the labels committed as
fixtures. This is a prerequisite, not a follow-up, because it is what separates an
evaluation from a demonstration.

The fixtures serve three purposes: they let agent output be scored per rule ID rather
than assessed impressionistically; they turn the framework's multi-model comparison
(`examples/taskflows/example_model_comparison.yaml`) into a measurement harness over a
fixed corpus; and they act as a regression test when a model version or the Trivy
ruleset changes.

Labels are recorded per finding with four fields: the verdict, the documents relied on
(`evidence`), a self-assessed `difficulty` of `easy` or `hard`, and a written rationale.
`evidence` exists so that Decision 7's comparison can measure whether the agent reached a
verdict *for the same reason* a human did, rather than only whether it landed on the same
answer — with a corpus this small, that distinction carries more signal than the
agreement rate itself. Labels are assigned and committed before any triage run exists;
verdicts formed with knowledge of agent output cannot support an agreement figure.

**Caveat recorded honestly:** the corpus is small and, more importantly, narrow. Of 12
first-party findings, 9 concern S3 posture on two buckets, 7 of them on the Terraform
state bucket alone:

```
  7  bootstrap state bucket   AWS-0086/0087/0089/0091/0093/0094/0132
  2  ssm scratch bucket       AWS-0089/0090
  2  public subnets           AWS-0164 x2
  1  VPC flow logs            AWS-0178
```

There are roughly four distinct judgment calls here, not twelve; deciding the state
bucket's posture settles seven findings at once. Most rules fire exactly once, so
per-rule agreement is barely a measurement. This is adequate to validate the *mechanism*
and inadequate to support any generalised accuracy claim, and every reported figure must
say so.

Two mitigations, both cheap: findings are labelled independently rather than per resource,
and each carries a `difficulty`, so that disagreement on a finding the human found easy
is distinguishable from disagreement on a hard one. The latter is a weaker claim than an
accuracy rate but an honest one. The corpus becomes genuinely interesting once
`live/gitlab/` exists and contributes RDS, ElastiCache and load balancer findings.

### 6. Autonomy as a ratchet, gated on measurement

```
  phase 1: PROPOSE            phase 2: DISMISS (scoped)      phase 3: DISMISS (broad)
  agent writes verdicts       auto-dismiss only for rule      allowlist widened as
  to a PR comment;            IDs at 100% fixture             evidence accumulates
  human applies them          agreement; others still
                              proposed
```

The agent starts with no write authority over alert state. Authority is granted per rule
ID, and only where measured agreement justifies it.

Rationale: a triage agent that wrongly dismisses a real finding is worse than no scanner,
because it manufactures confidence. Autonomy is therefore treated as something earned
against evidence rather than configured. The ratchet is also the most transferable part
of this design — "we let a model triage" is not a case anyone can take to a security
review; "here is per-rule agreement and here is the policy gating autonomy on it" is.

### 7. ADRs and design docs are agent context

`docs/adr/` and `docs/design/` are supplied to the triage agent alongside each finding.

This is the pipeline's actual differentiator over a suppression file. A rule engine
cannot know that a permissive egress rule is intentional per `ADR-0004`; a model with the
ADR in context can. The evaluation should measure this directly by running the same
corpus with and without doc context — a null result is itself a useful finding, since it
would say the value is in the model rather than in the repo's documentation discipline
(and would weaken the case for transferring this to teams without ADRs).

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
the wrong place to start: with no scanner baseline there is no ground truth, so no
agreement rate, so nothing measurable. Starting where the agent can be scored is what
makes the result defensible. Phase 2, once false-dismissal behaviour on Terraform is
characterised.

### 10. seclab-taskflow-agent, using its generic half only

The framework splits cleanly into a generic engine (personalities, taskflows, toolboxes,
checkpointing, multi-model comparison) and CodeQL-oriented security content. Only the
engine is used; CodeQL supports neither HCL nor Ansible and is irrelevant here.

The engine supplies exactly the primitives this pipeline needs, so the whole pipeline is
one declarative file rather than bespoke glue:

```
  task 1   run:      trivy config --format json | normalise + fingerprint
           outputs:  {first_party: [...], vendored: [...]}   <- JSON Schema validated
                        |
  task 2   over:     outputs.first_party
           agents:   [iac_triage_agent]  + ADR/design context
           outputs:  {verdict, confidence, rationale}
                        |
  task 3   run:      emit SARIF; gh api dismissals; gh issue create
```

`run:` (shell tasks), `outputs:` (schema-validated structured objects) and `over:`
(fan-out) are demonstrated in `examples/taskflows/example_typed_outputs.yaml`.

*Alternative considered:* a skill driven by Claude Code, already configured in this repo
and requiring no new dependency. Rejected for this change specifically because the goal
includes producing a reproducible, unattended, auditable pipeline whose definition can be
reviewed as an artefact — which is what the YAML buys. For interactive one-off triage the
skill would be the better tool.

## Risks / Trade-offs

- **Agent dismisses a genuine finding** → Phase 1 grants no dismissal authority at all;
  phase 2 grants it per rule ID only where fixture agreement is 100%. Dismissals stay
  visible and reversible in code scanning rather than being deleted.
- **Fixture corpus too small to generalise (20 findings, 8 of one rule)** → Treated as
  mechanism validation, not an accuracy claim; Decision 5 requires stating this wherever
  numbers are reported.
- **Ordinal fingerprints mis-attribute after sibling reordering** → Accepted and
  documented (Decision 3); the fixture set detects it when it happens.
- **Static scanning misses variable-dependent misconfigurations** → Known and observable
  today (`var.domain`); the plan-JSON path stays open (Decision 8).
- **Triage quality depends on ADR quality** → Made explicit and measurable by the
  with/without-context comparison (Decision 7) rather than assumed.
- **New dependency on a young, single-org framework** → Confined to orchestration.
  Scanner, sinks and fixtures are framework-independent, so replacing the engine would
  not invalidate the corpus or the routing design.
- **Inference cost and CI latency per PR** → 40% cut deterministically before inference;
  if the remainder is still too slow, triage moves to `main` and to a scheduled run,
  leaving only the raw Trivy upload on PRs.
- **`AI_API_TOKEN` in a public repo** → Repository secret, unavailable to fork PRs by
  design; the triage stage must be structured so fork PRs degrade to scan-and-upload
  rather than failing.

## Migration Plan

There is no existing behaviour to migrate. Deployment is ordered so each stage is useful
alone and the next is only reached if the previous holds:

1. Trivy in CI, SARIF uploaded to code scanning. Independently valuable; no agent, no
   secrets, no AWS access.
2. Normalisation, fingerprinting and the ownership partition, verified against the
   current corpus.
3. Hand-labelled fixtures committed.
4. Triage taskflow in propose-only mode, scored against fixtures.
5. Scoped dismissal authority for rules that met the bar in step 4.

**Rollback:** each stage is additive and independently revertible. Removing the triage
workflow leaves the Trivy scan intact; removing everything leaves the repo as it was,
since no scanner output is load-bearing for any other process.

## Open Questions

- Whether triage runs per-PR or on a schedule against `main`. Depends on measured latency
  and cost from step 4, and changes no spec, decision, or task.
- Whether the fixture set is regenerated or hand-merged when Trivy's ruleset introduces
  new rules. Answerable the first time it happens.
- Which specific dismissal reason code best represents "upstream, vendored module" in the
  code scanning API. A presentation detail within Decision 4.
