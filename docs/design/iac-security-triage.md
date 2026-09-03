# Agentic IaC security triage — as built

Status: **implemented, 39/41 tasks**. Records the shape the pipeline actually
took, the decisions that are load-bearing in the code, and the constraints that
must survive the next change to it. The change that produced it is
`openspec/changes/add-iac-security-triage/`; the behaviour contract is
`openspec/specs/iac-security-triage/spec.md`.

Note for whoever reads this next, human or otherwise: `docs/adr/` and
`docs/design/` are supplied to the triage agent as prompt context, so **this file
is itself agent input** (Decision 7). It describes mechanism deliberately and
records no per-finding verdict — a document that named verdicts would hand the
agent the answers it is about to be scored against.

Goal: catch security misconfigurations in this repository's Terraform, decide
what each one *means here*, and record a rationale for every decision — while
keeping the amount of that judgment made without a human explicitly bounded and
earned rather than configured.

## Shape of the thing

Two arms that meet at the scorer. The left arm is deterministic and always runs;
the right arm costs money, needs a token, and is invoked by hand.

```
                    trivy config --format json .          v0.74.0, pinned
                              │
                              ▼
                       normalise.py                       one record per finding
                              │                           keyed, then filtered twice
              ┌───────────────┼───────────────┐
              │               │               │
         ┌────▼────┐   ┌──────▼──────┐  ┌─────▼────┐
         │ eligible│   │below_thresh │  │ vendored │
         │    9    │   │      3      │  │    8     │
         └────┬────┘   └──────┬──────┘  └─────┬────┘
              │               │               │
              │          open alert,      recorded
              │          untriaged,       upstream,
              │          no issue         never prompted
              │
       ┌──────┴────────────────────────┐
       │                               │
       ▼                               ▼
  GitHub code scanning            taskflow/            ← the only model step
  human triage happens here       one branch per       Anthropic Messages API
       │                          eligible finding     no toolboxes at all
       ▼                               │
  export_fixture.py                    ▼
       │                        collect_verdicts.py    applies the discard rule
       ▼                               │
  fixtures/ground-truth.yaml           │
       │                               │
       └──────────►  score.py  ◄───────┘               agreement per rule,
                        │                              each figure with its n
                        ▼
                   autonomy.py                         the only thing that may
                        │                              write alert state
                        ▼
                  file_issues.py                       one issue per triaged
                                                       finding, under needs-triage
```

`normalise.py` reads stdin or a report path, so the committed baseline replays
without a scanner and the whole left arm is testable with neither Trivy nor AWS.

## Decisions that are load-bearing in the code

**Ownership first, severity second, and neither is a judgment.** Both filters are
path and enum comparisons; no model sees a finding before both have run. The
*order* is what matters: all 8 `CRITICAL` findings in this repository are
vendored, so a severity gate applied alone would admit exactly the eight findings
that cannot be fixed here and drop five first-party ones. Ownership is decided on
the **owner path** — the first `Occurrences[].Filename`, falling back to the Trivy
target — which is where the offending code is *instantiated* rather than where it
lives, because that is what says whether this repository can fix it.
`.terraform/modules/` is vendored, `live/` and `modules/` are first-party, and an
unrecognised path is treated as first-party so nothing escapes triage by being
somewhere unexpected.

**Identity is a readable composite key**, not a hash:

    AWS-0089:module.bootstrap:aws_s3_bucket.terraform_state_bucket

`ruleId:module_address:resource_type.resource_name`. It survives line-number
drift, distinguishes two instantiations of one module, and is readable because it
appears in the committed fixture and in issue bodies. There is no ordinal, so two
first-party findings could in principle collide; that case is *reported* as
`duplicate_first_party_keys` rather than absorbed, and a test holds it empty.

**Code scanning holds per-finding state; Issues hold the work.** Every triaged
finding becomes an issue whatever its verdict, because deciding a finding is not
worth acting on is precisely the judgment this pipeline exists to inform, and
burying it in a dismissal comment hides it from where work is reviewed.

**Ground truth is harvested from real triage, not authored beside it.**
`export_fixture.py` joins verdicts back out of dismissal comments and promoted
issues. There is no hand-labelling worksheet, because a second store is a second
place a verdict can be authored. Every entry carries `verdict_author`, and only
`human` entries may contribute to an agreement figure — a verdict written by a
model cannot score that model.

**Autonomy is a ratchet gated on agreement *and* support.** Dismissal without a
human requires all three of `agreement == 100%`, `scored >= support_floor`, and
the rule being allowlisted. The support floor is the load-bearing half: most
rules here fire exactly once, so an agreement-only gate would hand permanent
dismissal authority to a rule on the strength of a single case going the right
way. `k = 5` is a judgment, not a derivation. The allowlist is necessary and not
sufficient — evidence is re-checked at run time, so a grant that outlives its
evidence is an error rather than an honoured permission. See
`docs/adr/0007-autonomous-alert-dismissal-is-earned-per-rule.md`.

**The agent has no tools.** `toolboxes` is empty and deliberately so. Every fact
arrives in the prompt, which buys three things: a run reproducible from its
inputs, no structural path from a run to a dismissal or an issue whatever a
prompt says, and an agent that cannot read the verdict it is about to be scored
against. Read-only access would not have been enough for the third.

**Scanning is automatic; triage is invoked.** A code change never assigns a
verdict. `workflow_dispatch` is the *only* trigger on the triage workflow, which
is a security boundary and not a preference — see Hard constraints.

## Hard constraints (violate these and it breaks)

- **`workflow_dispatch` stays the only trigger on `iac-security-triage.yml`.**
  It is the one workflow that reads `AI_API_TOKEN`. A fork PR cannot reach a
  secret in a workflow it cannot trigger; adding `pull_request`, `push` or
  `schedule` undoes that in one line. If a timer is ever wanted, it goes in its
  own workflow.
- **The job that runs the model never holds `issues: write`; the job that files
  issues never sees the token.** The split across `triage` and `file-issues` is
  the containment, and `tests/test_workflows.py` asserts it per job.
- **No workflow gets `security-events: write` for triage.** Standing authority
  to close alerts is not something to hold while the allowlist is empty. It
  becomes a wiring question when a rule first clears the floor, and not before.
- **`ready-for-agent` is never applied by the pipeline.** That label authorises
  unattended remediation, so an agent able to apply it would be authorising its
  own downstream work. It is absent from the emittable vocabulary and a label
  outside that vocabulary raises rather than being filed.
- **The scan workflow must not reference the triage workflow.** Triage being
  broken, unfunded or unrun must never stop a finding being published.
- **`export_fixture.py` refuses to run once `runs/` is non-empty.** A fixture
  written after a triage run is not independent of it. `taskflow/.agent-data/` is
  deliberately not `runs/` so scratch state cannot spend that guard.
- **Below threshold means untriaged, never dismissed.** Dismissal is a verdict
  and none has been formed. Those findings keep their key, so lowering the
  threshold extends the corpus rather than resetting it — as it did at MEDIUM.
- **A verdict without a rationale is discarded, and discarded is not dropped.**
  The finding survives as `undetermined` carrying `discarded_verdict` and
  `discarded_because`. A finding that vanished from a run would be invisible to
  both scoring and the tracker.

## Consequence to carry forward

**There is no agreement figure, and there will not be one for this corpus.** All
9 fixture entries carry `verdict_author: model`: the eligible findings were
released to the agent untriaged, at the repo owner's instruction, for speed. The
scorer excludes every entry on provenance and reports nothing — which is the
honest outcome rather than a number. The forfeit is one-way, because a finding
the agent has judged can no longer be given an *independent* human verdict.

Measurement resumes over the below-threshold first-party findings, which the
agent has not been shown. That ordering constraint is binding, and it is why
`taskflow/` runs scoped by `globals.scope_keys` rather than over everything.
`docs/security/iac-triage-measurement.md` records what was given up and where it
resumes.

The corpus is also too narrow to carry an accuracy claim even once clean: 9
findings over 8 rules, 7 of which fire exactly once, reducing to roughly four
distinct judgment calls. This validates the *mechanism* and supports no claim
about accuracy — which is the direct reason autonomy needs a support floor rather
than an agreement threshold alone. It becomes genuinely interesting once
`live/gitlab/` contributes RDS, ElastiCache and load balancer findings.

## Owed artifacts

- **5.2 — the ADR-context ablation.** Run the corpus with and without doc context
  and record the delta, reporting both verdict agreement and whether the agent
  cited the same documents recorded in each finding's `evidence`. Deferred: over
  ~4 distinct judgment calls the delta is not separable from noise. The control
  arm is already wired as `context.py --without-context`, so it costs a flag
  rather than a rewrite.
- **5.3 — the multi-model comparison.** Blocked twice: it needs per-model
  agreement, which needs a human-assigned reference that does not currently
  exist.
- **Plan-JSON scanning** (Decision 8) and **non-Terraform IaC** — Ansible, shell,
  `user_data` (Decision 9) — both deferred, static HCL only today.
- **The dismissal wiring**, when a rule first clears the support floor.

## Boundaries worth keeping

Everything under `security/iac-security-triage/` is stdlib Python: no framework,
no network, no cloud credentials. `taskflow/` is the single exception and the
boundary is deliberate — it holds the only part needing
`seclab-taskflow-agent`, Docker and a model token, so replacing the orchestration
engine touches that directory and nothing else. The scanner, the identity scheme,
the fixtures and the scoring do not know it exists.

`vocabulary.py` defines the four verdict classes once, shared by the fixture
schema, the scorer and the personality, so they cannot drift apart. `upstream` is
kept out of that set: ownership is decided by path, not by triage, so it is not a
verdict.

The model is selected in `taskflow/model_configs/iac_triage.yaml` — Anthropic's
Messages API via `backend: anthropic_sdk`, not the framework's Copilot default.
The `endpoint` field is what makes authentication correct: the framework's
`get_provider()` does not recognise `api.anthropic.com`, so the token goes out as
`x-api-key` rather than as a bearer token that endpoint would reject. Swapping
models is a one-line edit to `models:`.

## Verification

    python3 -m unittest discover -s security/iac-security-triage/tests           # 100
    python3 -m unittest discover -s security/iac-security-triage/taskflow/tests  #  62

Both suites are offline — no Trivy, no AWS, no Docker, no model token, no
network. They run against the committed baseline, and the tests that matter most
*derive* their expectations from it rather than restating them, so they move when
the corpus does: that no rule clears the support floor, that no first-party key
is claimed twice, and that the fork boundary holds per job.

## Sources

- `openspec/specs/iac-security-triage/spec.md` — the behaviour contract
- `openspec/changes/add-iac-security-triage/design.md` — Decisions 1–11, with the
  rejected alternatives this document omits
- `security/iac-security-triage/README.md` — the deterministic arm, in operating detail
- `security/iac-security-triage/taskflow/README.md` — the agentic arm, ditto
- `docs/security/iac-triage-measurement.md` — the forfeited corpus and where measurement resumes
- `docs/adr/0007-autonomous-alert-dismissal-is-earned-per-rule.md`
