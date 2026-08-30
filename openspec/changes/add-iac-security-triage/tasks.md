Ordered to follow the staged deployment in `design.md - Migration Plan`. Each group is
independently useful and independently revertible; do not start a group before the
previous one is verified.

## 1. Scanning and alert publication

- [x] 1.1 Add a CI workflow that runs Trivy config scanning over the repository and
      uploads SARIF to code scanning; verify by opening a pull request that touches a
      `.tf` file and confirming alerts appear annotated on the changed lines
- [ ] 1.2 Confirm the workflow requests only `security-events: write` and no cloud
      credentials, and verify a fork pull request completes successfully with findings
      reported
      (permissions confirmed by inspection: `contents: read` + `security-events: write`
      only, no cloud credentials referenced; fork-PR behaviour not yet verified against a
      real fork PR)
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

- [ ] 3.1 **Human task.** Triage the 7 triage-eligible alerts in GitHub code scanning —
      the first-party findings at `HIGH` or above, not all 12 first-party ones: dismiss
      with a comment carrying the rationale and the repo-relative paths of any ADRs or
      design docs relied on, or leave open for promotion to an issue. Judge each finding
      independently rather than deciding once per resource — five of the seven concern the
      same bucket, so this is the main place independence can be lost; verify all 7 alerts
      have a recorded outcome and a non-empty comment, and that no below-threshold alert
      was triaged
- [ ] 3.2 Implement the fixture export: read alert state via `gh api
      /repos/:owner/:repo/code-scanning/alerts`, join to normalised records by key, and
      emit `fixtures/ground-truth.yaml` with `verdict`, `rationale` and `evidence` per
      key; verify the fixture contains exactly 7 entries, that every key resolves to a
      *triage-eligible* finding in the baseline fixture, that no below-threshold or
      vendored finding appears, and that the export predates any triage run
- [ ] 3.3 Add schema validation for the fixture, constraining `verdict` to the vocabulary
      in `vocabulary.py` and requiring a non-empty `rationale`; verify it rejects a
      fixture with a misspelled verdict and one with an empty rationale
- [ ] 3.4 Implement the scoring tool that compares automated verdicts against the fixture
      and reports agreement per rule alongside the number of findings each figure covers;
      verify it against a *deliberately disagreeing* input — a copy of the fixture with
      known verdicts altered — and confirm it reports the expected sub-100% figure and the
      correct per-rule counts. Scoring the fixture against itself is not a sufficient
      test: it passes on a scorer that returns 100% unconditionally
- [ ] 3.5 Verify a finding from a rule absent from the fixture is excluded from agreement
      figures and flagged, using a synthetic record
- [ ] 3.6 Verify the export is repeatable rather than a one-off: lowering the threshold in
      configuration and re-running 3.1/3.2 over the newly eligible findings extends the
      fixture without invalidating existing entries (`design.md - Decision 5`)

## 4. Triage taskflow, propose-only

- [ ] 4.1 Stand up `seclab-taskflow-agent` via its Docker image and confirm the
      environment works by running the shipped echo taskflow
- [ ] 4.2 Write the IaC triage personality defining the verdict vocabulary and requiring
      a rationale; verify it against a single hand-picked finding
- [ ] 4.3 Write the taskflow: a `run:` task producing schema-validated `outputs` from the
      normaliser, and an `over:` task fanning out across the eligible findings; verify
      `openspec`-independent offline linting and schema validation pass
- [ ] 4.4 Supply `docs/adr/` and `docs/design/` as triage context; verify the run
      completes and at least one rationale cites a decision record
- [ ] 4.5 Verify a verdict produced without a rationale is discarded and recorded as
      undetermined, by testing with a deliberately non-compliant response
- [ ] 4.6 Verify no alert state changes during a full run — the agent's output is carried
      by the issues of group 6, not by dismissals
- [ ] 4.8 Add the triage workflow with `workflow_dispatch` as its **only** trigger
      (`design.md - Decision 11`); verify it is not reachable from any push, pull request
      or schedule event, that `AI_API_TOKEN` is referenced only by this workflow, and that
      a fork pull request therefore cannot cause it to run
- [ ] 4.9 Verify the scan workflow has no dependency on the triage workflow: findings are
      published on a pull request with triage never invoked
- [ ] 4.7 Verify the pipeline degrades safely by running with model access removed, and
      confirming scan findings are still published and affected findings left untriaged

## 5. Measurement

- [ ] 5.1 Score a full triage run against the fixture; record per-rule agreement in
      `docs/`, each figure stated alongside the number of findings it covers, and state
      the corpus-size and corpus-diversity caveats from `design.md - Decision 5` —
      including that the corpus is 7 findings over 6 rules, that 5 of those 6 rules fire
      exactly once, that it reduces to roughly two distinct judgment calls, and that the
      severity gate is what removed the two most independent of the original four
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

- [ ] 6.1 Implement promotion of **every** triaged finding to a GitHub issue
      (`design.md - Decision 4`), carrying the finding key, the verdict and the rationale
      in the body, filed under `needs-triage` from `docs/agents/triage-labels.md`; verify
      a full run over the baseline corpus produces 7 issues, one per eligible finding
- [ ] 6.2 Implement idempotency keyed on the finding key; verify a second run with
      unchanged verdicts creates no duplicate issues, and that a human-applied disposition
      label on an existing issue is left untouched by the second run
- [ ] 6.3 Verify findings judged not applicable **do** create an issue stating that verdict
      and its rationale, and that their alerts are not dismissed while their rule is
      absent from the group 7 allowlist
- [ ] 6.4 Verify the system never applies `ready-for-agent`: assert it is absent from the
      label vocabulary the issue-creation step is able to emit, and that a run in which
      every finding is judged a mechanical fix still files everything under `needs-triage`.
      This is the boundary the remediation successor change depends on
- [ ] 6.5 Verify below-threshold and vendored findings create no issue

## 7. Scoped autonomy

- [ ] 7.1 Add an explicit, reviewable allowlist of rule IDs permitted autonomous
      dismissal, populated only from rules that reached full agreement in 5.1 **over at
      least `k = 5` scored findings** (`design.md - Decision 6`); verify that on the
      current corpus the allowlist is empty, since the largest eligible rule (`AWS-0164`)
      is n=2
- [ ] 7.2 Implement dismissal for allowlisted rules with the rationale recorded on the
      alert; verify a dismissed alert remains visible and can be reopened
- [ ] 7.3 Verify a finding from a non-allowlisted rule leaves alert state unchanged and
      is presented for a human, covering the never-scored case, the scored-below-full
      case, and the fully-agreed-but-below-support case
- [ ] 7.4 Document the ratchet policy — both the agreement bar and the support floor,
      and why the floor is the load-bearing half — and the evidence behind the current
      allowlist in `docs/`; consider recording it as an ADR alongside the existing
      records
