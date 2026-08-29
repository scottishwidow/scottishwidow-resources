# iac-security-triage Specification

## Purpose

Detects security misconfigurations in this repository's infrastructure code and decides
what each one means for this system, recording a rationale for every decision and
constraining how much of that decision-making happens without a human.

## Requirements

### Requirement: Infrastructure code is scanned on every change

The system SHALL statically scan the repository's Terraform for security
misconfigurations whenever infrastructure code changes, and SHALL publish the results as
durable per-finding alert state that persists across runs.

Scanning SHALL NOT require cloud credentials or access to live infrastructure.

#### Scenario: Pull request touching Terraform

- **WHEN** a pull request modifies a `.tf` file
- **THEN** the scan runs against the pull request's code
- **AND** each finding is visible as an alert annotated on the changed lines

#### Scenario: Pull request from a fork

- **WHEN** a pull request originates from a fork and privileged credentials are therefore
  unavailable
- **THEN** the scan still runs and its findings are still reported
- **AND** the absence of credentials does not cause the run to fail

#### Scenario: No infrastructure code changed

- **WHEN** a change touches only documentation or planning artefacts
- **THEN** previously published alert state is left unchanged
- **AND** no finding is re-reported as new

### Requirement: Findings have a stable identity

The system SHALL assign each finding an identifier derived from the rule, the module
instance, and the resource it concerns, such that the identifier is unchanged by edits
that shift the finding's position in a file.

The identifier SHALL distinguish two findings that share a rule, a file, and a line but
arise from different module instances.

#### Scenario: Unrelated edit shifts line numbers

- **WHEN** a resource is edited so that findings below it move to different line numbers
- **THEN** those findings retain the identifiers they had before the edit
- **AND** any triage verdict already recorded against them still applies

#### Scenario: Same rule fires in two instances of one module

- **WHEN** a single module is instantiated twice and the same rule fires in each instance
- **THEN** the two findings receive different identifiers
- **AND** a verdict recorded for one is not applied to the other

#### Scenario: Resource is renamed

- **WHEN** a resource is renamed
- **THEN** its findings receive new identifiers
- **AND** they are presented for triage again rather than inheriting the previous verdict

### Requirement: Findings are classified by ownership before triage

The system SHALL determine, by inspecting the location of the offending code and without
consulting a language model, whether each finding lies in code maintained in this
repository or in a vendored third-party module.

Findings in vendored code SHALL be recorded as upstream and SHALL NOT be submitted for
agentic triage.

#### Scenario: Finding in a vendored registry module

- **WHEN** a finding's offending code lies in a third-party module resolved from a
  registry
- **THEN** the finding is recorded as upstream with that classification as its rationale
- **AND** no inference is performed for it

#### Scenario: Finding in first-party code

- **WHEN** a finding's offending code lies in a path maintained in this repository
- **THEN** the finding is submitted for triage

#### Scenario: Ownership cannot be determined

- **WHEN** a finding's location matches neither a known first-party nor a known vendored
  path
- **THEN** the finding is treated as first-party and submitted for triage
- **AND** the unrecognised location is surfaced for a human to review

### Requirement: Every triaged finding receives a verdict with a rationale

The system SHALL assign each first-party finding exactly one verdict from a fixed
vocabulary covering: not applicable or accepted risk, real with a mechanical fix, real
requiring human judgment, and undetermined.

Each verdict SHALL be accompanied by a recorded rationale that is retrievable after the
run. A verdict SHALL NOT be recorded without one.

Documented architecture decisions and design documents in this repository SHALL be
available to the triage step as context.

#### Scenario: Finding contradicted by a recorded architecture decision

- **WHEN** a finding concerns a configuration that an architecture decision record
  explicitly justifies
- **THEN** the verdict may be not applicable or accepted risk
- **AND** the rationale cites the decision record relied upon

#### Scenario: Triage cannot reach a conclusion

- **WHEN** the available context is insufficient to judge a finding
- **THEN** the verdict is undetermined
- **AND** the finding remains open for a human

#### Scenario: Rationale is unavailable

- **WHEN** a verdict is produced without an accompanying rationale
- **THEN** the verdict is discarded and the finding is treated as undetermined

### Requirement: Verdicts route to alert state and to the work tracker

The system SHALL record every verdict against the finding's alert state, and SHALL create
tracker items only for findings judged to require action.

Tracker items SHALL carry the triage label corresponding to their verdict, using this
repository's established triage label vocabulary.

#### Scenario: Finding judged not applicable

- **WHEN** a finding's verdict is not applicable or accepted risk
- **THEN** its alert is closed with the rationale recorded against it
- **AND** no tracker item is created

#### Scenario: Finding judged actionable

- **WHEN** a finding's verdict is real with a mechanical fix
- **THEN** its alert remains open
- **AND** a tracker item is created carrying the label denoting work ready for an
  unattended agent

#### Scenario: Finding judged to need human judgment

- **WHEN** a finding's verdict is real requiring human judgment
- **THEN** a tracker item is created carrying the label denoting work requiring a human

#### Scenario: Finding already has a tracker item

- **WHEN** a finding that already has an open tracker item is triaged again with an
  unchanged verdict
- **THEN** no duplicate tracker item is created

### Requirement: Triage accuracy is measured against a fixed corpus

The system SHALL maintain a set of human-assigned verdicts covering the findings present
when this capability was introduced, and SHALL support scoring automated verdicts against
that set, reporting agreement per rule.

Reported agreement figures SHALL be accompanied by the size of the corpus they are
computed over.

#### Scenario: Scoring a triage run

- **WHEN** automated verdicts are scored against the human-assigned set
- **THEN** agreement is reported broken down by rule
- **AND** each figure is reported alongside the number of findings it covers

#### Scenario: A new rule produces findings absent from the corpus

- **WHEN** a finding arises from a rule with no human-assigned verdict
- **THEN** it is excluded from agreement figures rather than counted as agreement
- **AND** it is flagged as needing a human verdict

### Requirement: Autonomous dismissal is earned per rule

The system SHALL NOT close a finding's alert without human action unless automated
verdicts for that finding's rule have been scored against the human-assigned corpus and
agreed on every case.

For all other rules, the system SHALL present its verdict for a human to apply, and SHALL
leave alert state unchanged.

Granting or revoking this authority for a rule SHALL be an explicit, reviewable change.

#### Scenario: Rule has not been scored

- **WHEN** a finding arises from a rule that has never been scored against the corpus
- **THEN** the verdict is presented for a human to apply
- **AND** the alert state is left unchanged

#### Scenario: Rule scored below full agreement

- **WHEN** a finding arises from a rule whose scored agreement is not total
- **THEN** the verdict is presented for a human to apply
- **AND** the alert state is left unchanged

#### Scenario: Rule granted autonomous dismissal

- **WHEN** a finding arises from a rule that has been scored at full agreement and
  explicitly granted authority
- **AND** its verdict is not applicable or accepted risk
- **THEN** its alert is closed automatically with the rationale recorded
- **AND** the closure remains visible and reversible

### Requirement: The pipeline degrades rather than fails

The system SHALL continue to report scan findings when the triage step cannot run.

#### Scenario: Inference is unavailable

- **WHEN** the triage step cannot run because model access is unavailable or fails
- **THEN** scan findings are still published as alert state
- **AND** the affected findings are left untriaged rather than being closed or discarded
