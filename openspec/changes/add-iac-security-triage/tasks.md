Ordered to follow the staged deployment in `design.md - Migration Plan`. Each group is
independently useful and independently revertible; do not start a group before the
previous one is verified.

## 1. Scanning and alert publication

- [x] 1.1 Add a CI workflow that runs Trivy config scanning over the repository and
      uploads SARIF to code scanning; verify by opening a pull request that touches a
      `.tf` file and confirming alerts appear annotated on the changed lines
- [ ] 1.2 Confirm the workflow requests only `security-events: write` and no cloud
      credentials, and that a fork pull request degrades as the spec's fork scenario
      describes: the scan runs, findings reach the run's output, the rejected SARIF upload
      does not fail the run, and no alert state is written. Assert the first three by test
      over the workflow file — permissions, absence of cloud credentials, and
      `continue-on-error` on the upload step — rather than by inspection, since each is a
      property of a file that can be edited
      (permissions confirmed by inspection: `contents: read` + `security-events: write`
      only, no cloud credentials referenced. Restated 2026-09-03: the original wording
      required a fork PR to complete "with findings reported", which the implementation
      cannot deliver and never intended to — a fork's `GITHUB_TOKEN` is read-only whatever
      the permissions block says, so `upload-sarif` is rejected and the step carries
      `continue-on-error: true`. Findings reach the job log, not alert state. That is the
      accepted degradation, and the inability of a fork PR to write alert state is a
      security property worth asserting rather than a shortfall. The test half is
      unimplemented; observing a real fork PR remains a one-off that needs a second
      account and blocks nothing.)
- [x] 1.3 Verify a documentation-only pull request does not re-report existing findings
      as new, by comparing alert numbers before and after
- [x] 1.4 Record the baseline scan output as a committed fixture; verify it contains 20
      findings across 11 rule IDs, matching the corpus described in `design.md - Context`

## 2. Normalisation, identity and ownership

- [x] 2.1 Implement the finding normaliser that reads Trivy JSON and emits one record per
      finding carrying rule ID, module address, resource type and name, and file path;
      verify it emits exactly 20 records from the baseline fixture
- [x] 2.2 Implement the composite key from `design.md - Decision 3`
      (`ruleId:module_address:resource_type.resource_name`, no hash, no ordinal); verify
      all 12 first-party keys are distinct, and that every one of the 8 colliding
      `AWS-0104` findings is vendored and therefore never carries a verdict
- [x] 2.3 Verify key stability by inserting a blank line above a finding in
      `live/management/main.tf`, re-running, and confirming every key is unchanged
- [x] 2.4 Verify key sensitivity by renaming a resource in a scratch branch and
      confirming only that resource's keys change
- [x] 2.5 Implement the ownership partition over `live/`, `modules/` and
      `.terraform/modules/`; verify it yields 12 first-party and 8 vendored findings on
      the baseline fixture
- [x] 2.6 Verify a finding whose path matches no known prefix is classified first-party
      and its location surfaced, using a synthetic record
- [x] 2.8 Implement the guard that replaces the ordinal: report any key claimed by more
      than one *first-party* finding as `duplicate_first_party_keys` rather than absorbing
      it; verify it is empty on the baseline fixture, that a synthetic first-party
      collision is reported, and that a vendored collision is not
- [x] 2.7 Retire the hand-labelling worksheet generator. Triage is performed in code
      scanning and the fixture exported from alert state (`design.md - Decision 5`), so a
      pre-filled YAML worksheet would be the second verdict store Decision 4 rejects;
      verify `worksheet.py`, its test and the unfilled worksheet fixture are removed and
      the suite still passes
- [x] 2.9 Implement the severity gate from `design.md - Decision 2`: applied *after* the
      ownership partition, with the threshold (`HIGH`) as a recorded configuration value
      rather than a literal in the partition logic. Verify against the baseline fixture
      that it yields **7 eligible, 5 below-threshold and 8 vendored** findings; that the
      7 eligible span 6 rule IDs with `AWS-0164` the only one at n=2; and that all 8
      `CRITICAL` findings are excluded on ownership, not admitted on severity
- [x] 2.10 Verify below-threshold findings survive the pipeline as untriaged records —
      present in the normaliser's output, carrying no verdict, and marked so that no
      downstream step files an issue for them

## 3. Ground truth

Triage before running the agent, not after. Verdicts assigned with knowledge of the
agent's output are contaminated and cannot support any agreement figure; performing the
triage in code scanning makes the ordering auditable in alert history rather than resting
on a commit timestamp.

3.1 records a deliberate exception: the original seven eligible findings were released to
the agent untriaged and are forfeited as a corpus. The rule is not weakened by that — it
binds 3.6, which is where measurement resumes over findings the agent has not been shown.

- [ ] 3.1 **Human task.** Triage the 7 triage-eligible alerts in GitHub code scanning —
      the first-party findings at `HIGH` or above, not all 12 first-party ones: dismiss
      with a comment carrying the rationale and the repo-relative paths of any ADRs or
      design docs relied on, or leave open for promotion to an issue. Judge each finding
      independently rather than deciding once per resource — five of the seven concern the
      same bucket, so this is the main place independence can be lost; verify all 7 alerts
      have a recorded outcome and a non-empty comment, and that no below-threshold alert
      was triaged
      (1 of 7 recorded so far, as issue #48 for alert #1 — and its verdict was written by
      a model at the repo owner's instruction, not by a human. That entry is marked
      `verdict_author: model` and cannot support an agreement figure; 3.2 must carry the
      field and 3.4 must exclude such entries from scoring. The remaining 6 are untriaged.

      **Forfeited by decision, 2026-09-03.** The remaining 6 alerts will not be triaged
      ahead of the agent. The propose-only pipeline runs first, and these 7 findings are
      given up as an evaluation corpus.

      What is forfeited is independence, not access. For an *open* alert the issue body
      **is** the verdict store — GitHub's API accepts a comment only alongside a
      dismissal, so `export_fixture.py` reads open-alert verdicts out of the issue the
      alert was promoted to (`issue_body.py`). Once group 6 files an issue per eligible
      finding, that issue's Verdict row already holds the agent's answer under
      `verdict_author: model`, and `score.py` counts only `human` entries. Recording a
      human verdict afterwards therefore means overwriting, in the same field of the same
      issue, the output that was to be scored — leaving nothing to compare against. There
      is no second slot. `evidence` is contaminated harder still: Decision 7 asks whether
      the agent reached a verdict *for the same reason*, and the ADRs would be cited after
      reading the agent cite them.

      What it costs is a mechanism check, not an accuracy figure. No rule in this corpus
      exceeds n=2, so group 7's support floor of 5 could never have opened on it whatever
      the agreement rate came out at. Measurement resumes at 3.6 over findings the agent
      was never shown — the 5 below-threshold first-party findings, alerts #16 and #10 at
      `MEDIUM` and #15, #6 and #3 at `LOW`, of which the two `MEDIUM` ones are the most
      independent judgments in the original set — and widens again when `live/gitlab/`
      lands. `export_fixture.py --allow-after-triage` exists for that re-export, not for
      retrofitting ground truth onto these 7.)
- [ ] 3.2 Implement the fixture export: read alert state via `gh api
      /repos/:owner/:repo/code-scanning/alerts`, join to normalised records by key, and
      emit `fixtures/ground-truth.yaml` with `verdict`, `rationale` and `evidence` per
      key; verify the fixture contains exactly 7 entries, that every key resolves to a
      *triage-eligible* finding in the baseline fixture, that no below-threshold or
      vendored finding appears, and that the export predates any triage run
      (`export_fixture.py` implemented and tested against the baseline corpus: a full
      export yields 7 entries, ineligible findings are reported rather than exported, and
      the export refuses to run once `runs/` exists. Entries additionally carry
      `verdict_author`, since the corpus is now mixed. The live export yields 1 of 7
      entries and stays unchecked until 3.1 supplies the remaining 6.
      Two things the task did not anticipate, both resolved in code: an *open* alert has
      nowhere to record a rationale — the API accepts a comment only with a dismissal — so
      an open finding's verdict is read from the issue it was promoted to, joined by the
      finding key in the issue body; and the two sides spell paths differently, since
      Trivy's `Target` composes the module instance into the path while the alert reports
      the module source, so the join falls back to filename when the exact path misses.

      **Live export forfeited with 3.1, 2026-09-03.** The implementation and its tests
      stand; what is given up is running it over the current corpus. This task's
      acceptance condition — a fixture of exactly 7 entries, exported before any triage
      run — is no longer reachable, since the 6 untriaged alerts will not receive an
      independent human verdict. The export itself is not abandoned: 3.6 is where it next
      runs for real, over the newly eligible findings after a threshold drop, and that
      run is what will demonstrate the export works against live alert state rather than
      against the baseline fixture alone.)
- [x] 3.3 Add schema validation for the fixture, constraining `verdict` to the vocabulary
      in `vocabulary.py` and requiring a non-empty `rationale`; verify it rejects a
      fixture with a misspelled verdict and one with an empty rationale
      (`fixture_schema.py`; also rejects an unknown `verdict_author`, duplicate keys and
      missing fields)
- [x] 3.4 Implement the scoring tool that compares automated verdicts against the fixture
      and reports agreement per rule alongside the number of findings each figure covers;
      verify it against a *deliberately disagreeing* input — a copy of the fixture with
      known verdicts altered — and confirm it reports the expected sub-100% figure and the
      correct per-rule counts. Scoring the fixture against itself is not a sufficient
      test: it passes on a scorer that returns 100% unconditionally
      (`score.py`; the disagreeing-run test asserts 50% overall, `AWS-0087` at 0% and
      `AWS-0164` at 50% over n=2 with the differing key named. It also excludes entries
      whose `verdict_author` is not `human`, so a partly model-authored fixture yields an
      honest figure over the part that is not — added scope beyond this task, forced by
      the model-authored entry recorded in 3.1.)
- [x] 3.5 Verify a finding from a rule absent from the fixture is excluded from agreement
      figures and flagged, using a synthetic record
      (reported as `unscored_rules`; the test asserts the unlabelled finding does not
      inflate the figure it is absent from)
- [ ] 3.6 Verify the export is repeatable rather than a one-off: lowering the threshold in
      configuration and re-running 3.1/3.2 over the newly eligible findings extends the
      fixture without invalidating existing entries (`design.md - Decision 5`)
      (this is now also where measurement *resumes*, not merely where repeatability is
      shown — see 3.1's forfeiture. The newly eligible findings are the only ones left
      that the agent has not already been shown, so the ordering constraint has to hold
      here even though it was spent for the original 7: triage the newly eligible alerts
      before the next triage run, not after.)

## 4. Triage taskflow, propose-only

- [ ] 4.1 Stand up `seclab-taskflow-agent` via its Docker image and confirm the
      environment works by running the shipped echo taskflow
      (image `ghcr.io/githubsecuritylab/seclab-taskflow-agent` v0.5.0 pulled and
      driven by `taskflow/run.sh`. The echo taskflow loads, resolves its
      personality and starts its MCP server, then stops at
      `AI_API_TOKEN environment variable is not set` — every leg of the
      environment is confirmed except the model call, which no token here can
      exercise. Two container-ergonomics fixes were needed and are in `run.sh`:
      the data directory is bound under `/data` rather than the image's default
      `/root/.local/share`, since `/root` is mode 700 and an unprivileged user
      cannot traverse into a mount beneath it, and the container runs as the
      invoking user so the manifest does not come back root-owned.)
- [ ] 4.2 Write the IaC triage personality defining the verdict vocabulary and requiring
      a rationale; verify it against a single hand-picked finding
      (`taskflow/personalities/iac_triage.yaml`. The vocabulary is held in step
      with `vocabulary.py` by a test rather than by care: a verdict class added
      to one and not the other fails the suite. Verification against a finding
      needs a model and is not done.)
- [x] 4.3 Write the taskflow: a `run:` task producing schema-validated `outputs` from the
      normaliser, and an `over:` task fanning out across the eligible findings; verify
      `openspec`-independent offline linting and schema validation pass
      (`taskflow/taskflows/iac_triage.yaml`; `run.sh --lint --strict` reports no
      issues. Both `outputs` schemas were also validated against real data by a
      live run — the manifest shows `findings.eligible` at 7 records and
      `context.documents` at 7 — so this is schema validation exercised, not
      merely linted. Two constraints the task did not anticipate, both resolved:
      a `run:` field is *not* Jinja-templated, so configuration reaches the shell
      tasks through `env:`, which is; and the framework resolves a dotted name
      with `importlib.resources.files()`, so every path component must be a legal
      Python identifier — `iac-security-triage` is not, which is why `run.sh`
      enters `taskflow/` and addresses `taskflows.iac_triage` from below the
      hyphen.)
- [ ] 4.4 Supply `docs/adr/` and `docs/design/` as triage context; verify the run
      completes and at least one rationale cites a decision record
      (`taskflow/context.py` collects all 7 documents and a live run captured
      them into the manifest, so the context reaches the prompt. The framework
      ships no filesystem toolbox, so context is pushed into the prompt rather
      than fetched by the agent — which is the stricter arrangement: the agent
      has no tools at all, so it cannot read the alert state holding a verdict it
      is about to be scored against. `--without-context` is wired now as the
      control arm 5.2 will need. Whether a rationale cites a record needs a
      model.)
- [x] 4.5 Verify a verdict produced without a rationale is discarded and recorded as
      undetermined, by testing with a deliberately non-compliant response
      (enforced twice and tested against six non-compliant responses: absent
      rationale, whitespace-only rationale, verdict outside the vocabulary, a
      branch that produced nothing, a non-JSON reply, and a JSON string. The
      taskflow's `outputs` schema rejects the branch, and
      `collect_verdicts.py` applies the rule again over every branch — the schema
      cannot catch a whitespace-only rationale or a branch that failed for an
      unrelated reason, and the property should not rest on one line of YAML
      staying right. Discarded is not dropped: the finding is still reported, as
      `undetermined`, carrying `discarded_verdict` and `discarded_because`.)
- [ ] 4.6 Verify no alert state changes during a full run — the agent's output is carried
      by the issues of group 6, not by dismissals
      (structurally true and asserted by test rather than observed: the agent is
      given no toolboxes at all, so there is no path from a run to a dismissal
      whatever a prompt says, and the triage workflow requests only
      `contents: read`. Both are held by tests. Observed across two runs that
      reached the model boundary — all 20 alerts still `open` afterwards — but a
      *full* run needs a token, so the task stays open.)
- [x] 4.8 Add the triage workflow with `workflow_dispatch` as its **only** trigger
      (`design.md - Decision 11`); verify it is not reachable from any push, pull request
      or schedule event, that `AI_API_TOKEN` is referenced only by this workflow, and that
      a fork pull request therefore cannot cause it to run
      (`.github/workflows/iac-security-triage.yml`, verified by
      `taskflow/tests/test_workflows.py` rather than by inspection, since the
      token argument holds only while the trigger list stays exactly
      `workflow_dispatch`: the tests assert that, name `push`,
      `pull_request`, `pull_request_target` and `schedule` explicitly as absent,
      and assert that no other workflow file mentions `AI_API_TOKEN`. The
      workflow also requests only `contents: read`, so propose-only is enforced
      by permissions and not only by the agent having no tools.)
- [x] 4.9 Verify the scan workflow has no dependency on the triage workflow: findings are
      published on a pull request with triage never invoked
      (already true in the live repo and now held by test: all 20 alerts were
      published by the scan workflow before the triage workflow existed, so
      "published with triage never invoked" is a matter of record. The tests
      assert the scan declares no `needs`, no `workflow_call` and no
      `workflow_run`, and does not name the triage workflow file — checked by
      filename rather than by substring, since the scan legitimately mentions
      `security/iac-security-triage/` in a comment about the baseline fixture.)
- [x] 4.7 Verify the pipeline degrades safely by running with model access removed, and
      confirming scan findings are still published and affected findings left untriaged
      (run for real rather than simulated — this environment has no
      `AI_API_TOKEN`. Both deterministic tasks completed, the `verdicts` task
      failed with `AI_API_TOKEN environment variable is not set`, the run
      manifest recorded `status: failed` with the findings and context outputs
      intact, and all 20 alerts remained `open` and published. One consequence
      worth recording: `collect_verdicts.py` refuses a manifest with no verdicts
      rather than writing an empty file, because an empty file in `runs/` would
      tell `export_fixture.py` that triage had happened and ground truth could no
      longer be recorded independently. A run that produced nothing must not
      spend that guard; a test holds this.)

## 5. Measurement

- [ ] 5.1 **Forfeited with 3.1**, 2026-09-03. Score a full triage run against the fixture; record per-rule agreement in
      `docs/`, each figure stated alongside the number of findings it covers, and state
      the corpus-size and corpus-diversity caveats from `design.md - Decision 5` —
      including that the corpus is 7 findings over 6 rules, that 5 of those 6 rules fire
      exactly once, that it reduces to roughly two distinct judgment calls, and that the
      severity gate is what removed the two most independent of the original four
      (no independent fixture exists for this corpus, so there is no agreement figure to
      record — `score.py` would exclude every entry as non-human-authored and report an
      empty result, which is the honest outcome rather than a number. The residual worth
      writing to `docs/` is the forfeiture itself: which findings were given up, why
      ordering made it one-way, and that measurement resumes at 3.6. The scorer, its
      disagreement test and the caveats enumerated above are unaffected and still apply
      the moment a clean corpus exists.)
- [ ] 5.2 **Deferred** until the corpus widens (`design.md - Decision 7`). Run the same
      corpus with and without ADR context and record the delta, reporting both verdict
      agreement and whether the agent cited the same documents recorded in each finding's
      `evidence` field, whether or not the result favours including context. Over roughly
      four distinct judgment calls the delta is not separable from noise; `evidence` is
      captured from 3.2 onward so this is runnable the moment the corpus can carry it
- [ ] 5.3 **Deferred** until the corpus widens. Run the multi-model comparison over the
      fixed corpus and record per-model agreement; verify each model is scored over the
      identical finding set

## 6. Routing to the tracker

- [x] 6.1 Implement promotion of **every** triaged finding to a GitHub issue
      (`design.md - Decision 4`), carrying the finding key, the verdict and the rationale
      in the body, filed under `needs-triage` from `docs/agents/triage-labels.md`; verify
      a full run over the baseline corpus produces 7 issues, one per eligible finding
      (`file_issues.py`, in the body shape `issue_body.py` already reads back, so
      the issue an alert is promoted to remains the verdict store `export_fixture.py`
      joins to. Verified against the baseline corpus rather than asserted: a full
      run plans exactly 7 issues, one per eligible key, each carrying the key, the
      verdict and the rationale. Filing was wired into CI as a *separate job* —
      added scope the task did not name, but the alternative was giving the job
      that runs the model `issues: write`. The job holding that permission sees no
      model and no token; the job that runs the agent cannot open an issue.
      One thing the task did not anticipate: a verdict whose rationale
      `collect_verdicts.py` discarded arrives with an empty rationale by design,
      so the issue states what was discarded and why rather than filing a blank
      section.)
- [x] 6.2 Implement idempotency keyed on the finding key; verify a second run with
      unchanged verdicts creates no duplicate issues, and that a human-applied disposition
      label on an existing issue is left untouched by the second run
      (the key is read back out of existing issue bodies, so identity comes from
      the same field everything else joins on rather than from a title convention.
      A second run over the 7 issues plans nothing, and a *changed* verdict for a
      known key still plans nothing — the key is the identity, not the verdict.
      The human label survives because the plan has no instruction that could
      reach an existing issue, which the test asserts as an absence rather than
      trusting a conditional. Issues are fetched `--state all`, so a finding closed
      as `wontfix` is not refiled.)
- [x] 6.3 Verify findings judged not applicable **do** create an issue stating that verdict
      and its rationale, and that their alerts are not dismissed while their rule is
      absent from the group 7 allowlist
      (a run in which all 7 verdicts are `not-applicable` files all 7. The
      no-dismissal half is held structurally rather than conditionally: the module
      never speaks to the code scanning API, asserted by a test over its own
      source, and its CI job is not granted `security-events`. There is no code
      path from a verdict to a dismissal for an allowlist to have to gate.)
- [x] 6.4 Verify the system never applies `ready-for-agent`: assert it is absent from the
      label vocabulary the issue-creation step is able to emit, and that a run in which
      every finding is judged a mechanical fix still files everything under `needs-triage`.
      This is the boundary the remediation successor change depends on
      (`EMITTABLE_LABELS` is `("needs-triage",)` and a label outside it raises
      `ForbiddenLabel` before any `gh` call, so the guard holds on the filing path
      and not only on the plan. Tested over *every* verdict in the vocabulary
      rather than the mechanical one alone: no verdict class unlocks a different
      label.)
- [x] 6.5 Verify below-threshold and vendored findings create no issue
      (neither group is ever a candidate, and a verdict arriving for one is
      reported as `ineligible_verdicts` and exits non-zero rather than being
      filed — honouring such a verdict would defeat the gate that excluded it.
      A partial run additionally reports the eligible findings it left untriaged,
      so a finding missing an issue is visible rather than inferred from a count.)

## 7. Scoped autonomy

- [x] 7.1 Add an explicit, reviewable allowlist of rule IDs permitted autonomous
      dismissal, populated only from rules that reached full agreement in 5.1 **over at
      least `k = 5` scored findings** (`design.md - Decision 6`); verify that on the
      current corpus the allowlist is empty, since the largest eligible rule (`AWS-0164`)
      is n=2
      (`autonomy.json` holds the floor and the allowlist; the allowlist is empty.
      The emptiness is *derived* rather than asserted: a test computes the largest
      eligible rule from the baseline corpus, gets 2, and checks it against the
      floor — so widening the corpus moves the test instead of falsifying it.
      One thing built beyond the task, because "populated only from rules that
      reached full agreement" is otherwise a comment: the allowlist is necessary
      and not sufficient. Evidence is re-checked at run time against the scoring
      report, so a grant that outlives its evidence is reported as an error
      rather than honoured, and the file can only narrow what the measurement
      permits. Note 5.1 has not run, so the allowlist is empty for two
      independent reasons — no rule can reach n=5, and there is no agreement
      figure at all yet.)
- [x] 7.2 Implement dismissal for allowlisted rules with the rationale recorded on the
      alert; verify a dismissed alert remains visible and can be reopened
      (`autonomy.py --apply` PATCHes the alert to `dismissed` with
      `dismissed_reason: won't fix` — not `false positive`, since a finding that
      does not apply here is not a scanner error — and a comment carrying the
      agent's rationale, the rule, the finding key and the fact that reopening
      withdraws the closure. Reversibility is a real operation rather than a
      claim: `--reopen <alert>` PATCHes it back. Visibility and reversal are
      asserted structurally, on the request shape — the call is an edit and
      never a delete — because verifying them against live alerts needs a rule
      that has earned dismissal and there is none.
      Deliberately **not** wired into CI. No workflow is granted
      `security-events: write` for triage and a test asserts that per job:
      standing authority to close alerts is not worth holding while the
      allowlist is empty. That becomes a wiring question when a rule first
      clears the floor.)
- [x] 7.3 Verify a finding from a non-allowlisted rule leaves alert state unchanged and
      is presented for a human, covering the never-scored case, the scored-below-full
      case, and the fully-agreed-but-below-support case
      (all three, each with its own distinct reason on the decision so a human
      reading the report can tell "never measured" from "measured and
      disagreed". Two more cases the task did not enumerate are covered because
      the code has to handle them: a grant whose evidence has gone stale, and a
      verdict that was never `not-applicable` — tested across every other class
      in the vocabulary. The end-to-end case is the one that matters: every
      eligible finding judged `not-applicable` and scored at 100% on every rule,
      against the committed policy, dismisses nothing — all 7 withheld on the
      support floor.)
- [x] 7.4 Document the ratchet policy — both the agreement bar and the support floor,
      and why the floor is the load-bearing half — and the evidence behind the current
      allowlist in `docs/`; consider recording it as an ADR alongside the existing
      records
      (`docs/adr/0007-autonomous-alert-dismissal-is-earned-per-rule.md`, recorded
      as an ADR because the number `k = 5` is a judgment someone will later want
      to lower and the reasoning has to outlive whoever made it. It states both
      bars, why the agreement bar is the one that looks strict and is in fact
      almost free at n=1, and the evidence behind the empty allowlist — including
      that the fixture's single entry is model-authored and excluded, so the
      corpus supports no agreement figure at all today. Being under `docs/adr/`
      it is now also triage context, so the agent reads the policy governing it.)
