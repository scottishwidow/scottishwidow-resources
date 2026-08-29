Ordered to follow the staged deployment in `design.md - Migration Plan`. Each group is
independently useful and independently revertible; do not start a group before the
previous one is verified.

## 1. Scanning and alert publication

- [ ] 1.1 Add a CI workflow that runs Trivy config scanning over the repository and
      uploads SARIF to code scanning; verify by opening a pull request that touches a
      `.tf` file and confirming alerts appear annotated on the changed lines
- [ ] 1.2 Confirm the workflow requests only `security-events: write` and no cloud
      credentials, and verify a fork pull request completes successfully with findings
      reported
- [ ] 1.3 Verify a documentation-only pull request does not re-report existing findings
      as new, by comparing alert numbers before and after
- [ ] 1.4 Record the baseline scan output as a committed fixture; verify it contains 20
      findings across 11 rule IDs, matching the corpus described in `design.md - Context`

## 2. Normalisation, identity and ownership

- [ ] 2.1 Implement the finding normaliser that reads Trivy JSON and emits one record per
      finding carrying rule ID, module address, resource type and name, and file path;
      verify it emits exactly 20 records from the baseline fixture
- [ ] 2.2 Implement the fingerprint from `design.md - Decision 3` (stable core plus
      ordinal); verify all 20 fingerprints are distinct, in particular that the four
      colliding `AWS-0104` findings receive four different identifiers
- [ ] 2.3 Verify fingerprint stability by inserting a blank line above a finding in
      `live/management/main.tf`, re-running, and confirming every fingerprint is unchanged
- [ ] 2.4 Verify fingerprint sensitivity by renaming a resource in a scratch branch and
      confirming only that resource's fingerprints change
- [ ] 2.5 Implement the ownership partition over `live/`, `modules/` and
      `.terraform/modules/`; verify it yields 12 first-party and 8 vendored findings on
      the baseline fixture
- [ ] 2.6 Verify a finding whose path matches no known prefix is classified first-party
      and its location surfaced, using a synthetic record
- [ ] 2.7 Implement the labelling worksheet generator, emitting one YAML entry per
      first-party finding pre-filled with fingerprint, rule, title, severity, module,
      resource, location, remediation text and the offending code, and with empty
      `verdict`, `evidence`, `difficulty` and `rationale` fields; verify it emits 12
      entries from the baseline fixture and that no human field is pre-populated

## 3. Ground truth

Label before running the agent, not after. Verdicts assigned with knowledge of the
agent's output are contaminated and cannot support any agreement figure; committing the
labels first makes the ordering auditable in git history.

- [ ] 3.1 **Human task.** Fill in `verdict`, `evidence`, `difficulty` and `rationale` for
      each of the 12 first-party findings in the generated worksheet, judging each
      finding independently rather than deciding once per resource; verify every entry
      has all four fields populated
- [ ] 3.2 Commit the completed worksheet as the ground-truth fixture, keyed by
      fingerprint, before any triage run exists; verify every key resolves to a
      first-party finding in the baseline fixture and that the commit predates group 4
- [ ] 3.3 Add schema validation for the fixture, constraining `verdict` and `difficulty`
      to their enumerations and requiring a non-empty `rationale`; verify it rejects a
      fixture with a misspelled verdict
- [ ] 3.4 Implement the scoring tool that compares automated verdicts against the
      fixtures and reports agreement per rule alongside the count each figure covers,
      broken down by `difficulty`; verify it reports 100% when scored against the
      fixtures themselves
- [ ] 3.5 Verify a finding from a rule absent from the fixtures is excluded from
      agreement figures and flagged, using a synthetic record

## 4. Triage taskflow, propose-only

- [ ] 4.1 Stand up `seclab-taskflow-agent` via its Docker image and confirm the
      environment works by running the shipped echo taskflow
- [ ] 4.2 Write the IaC triage personality defining the verdict vocabulary and requiring
      a rationale; verify it against a single hand-picked finding
- [ ] 4.3 Write the taskflow: a `run:` task producing schema-validated `outputs` from the
      normaliser, and an `over:` task fanning out across first-party findings; verify
      `openspec`-independent offline linting and schema validation pass
- [ ] 4.4 Supply `docs/adr/` and `docs/design/` as triage context; verify the run
      completes and at least one rationale cites a decision record
- [ ] 4.5 Verify a verdict produced without a rationale is discarded and recorded as
      undetermined, by testing with a deliberately non-compliant response
- [ ] 4.6 Publish verdicts as a pull request comment only; verify no alert state changes
      during a full run
- [ ] 4.7 Verify the pipeline degrades safely by running with model access removed, and
      confirming scan findings are still published and affected findings left untriaged

## 5. Measurement

- [ ] 5.1 Score a full triage run against the fixtures; record per-rule agreement with
      corpus sizes in `docs/`, reported separately for findings labelled `easy` and
      `hard`, and state the corpus-size and corpus-diversity caveats from
      `design.md - Decision 5`
- [ ] 5.2 Run the same corpus with and without ADR context and record the delta, per
      `design.md - Decision 7`; report both verdict agreement and whether the agent cited
      the same documents recorded in each finding's `evidence` field, and report the
      result whether or not it favours including context
- [ ] 5.3 Run the multi-model comparison over the fixed corpus and record per-model
      agreement; verify each model is scored over the identical finding set

## 6. Routing to the tracker

- [ ] 6.1 Implement promotion of actionable verdicts to GitHub issues carrying the label
      from `docs/agents/triage-labels.md` matching the verdict; verify one issue per
      verdict class appears with the correct label
- [ ] 6.2 Implement idempotency keyed on fingerprint; verify a second run with unchanged
      verdicts creates no duplicate issues
- [ ] 6.3 Verify findings judged not applicable create no issue

## 7. Scoped autonomy

- [ ] 7.1 Add an explicit, reviewable allowlist of rule IDs permitted autonomous
      dismissal, populated only from rules that reached full agreement in 5.1; verify it
      is empty if no rule qualifies
- [ ] 7.2 Implement dismissal for allowlisted rules with the rationale recorded on the
      alert; verify a dismissed alert remains visible and can be reopened
- [ ] 7.3 Verify a finding from a non-allowlisted rule leaves alert state unchanged and
      is presented for a human, covering both the never-scored and the scored-below-full
      cases
- [ ] 7.4 Document the ratchet policy and the evidence behind the current allowlist in
      `docs/`; consider recording it as an ADR alongside the existing records
