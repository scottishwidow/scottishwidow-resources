## Purpose

Detects security misconfigurations in this repository's infrastructure code, selects
which of them are worth reasoning about, and decides what each one means for this system,
recording a rationale for every decision and constraining how much of that
decision-making happens without a human.

## ADDED Requirements

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

Two findings that share a rule, a module instance and a resource SHALL receive the same
identifier and SHALL be triaged as a single judgment. Where such findings lie in code
maintained in this repository, the system SHALL surface the shared identifier rather than
recording one verdict against both silently.

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

#### Scenario: Co-located findings of one rule on one resource

- **WHEN** a rule fires more than once on the same resource in the same module instance
- **THEN** those findings share an identifier and are triaged as one judgment
- **AND** if that code is maintained in this repository, the shared identifier is
  surfaced rather than silently applying one verdict to several judgments

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

### Requirement: Only findings above a severity threshold are triaged

The system SHALL apply a severity threshold to findings that survive ownership
classification, and SHALL submit for triage only those at or above it. The threshold
SHALL be a recorded configuration value rather than an implicit property of the code.

The threshold SHALL be applied after ownership classification and SHALL NOT replace it: a
finding in vendored code is excluded on ownership alone, whatever its severity.

Findings excluded by the threshold SHALL still be published as alert state, SHALL be left
untriaged rather than closed or discarded, and SHALL NOT produce a tracker item.

#### Scenario: First-party finding at or above the threshold

- **WHEN** a finding lies in code maintained in this repository and its severity is at or
  above the threshold
- **THEN** it is submitted for triage

#### Scenario: First-party finding below the threshold

- **WHEN** a finding lies in code maintained in this repository and its severity is below
  the threshold
- **THEN** it is not submitted for triage and no verdict is assigned
- **AND** its alert remains published and open
- **AND** no tracker item is created for it

#### Scenario: Vendored finding above the threshold

- **WHEN** a finding lies in vendored code and its severity is at or above the threshold
- **THEN** it is excluded on ownership and is not submitted for triage
- **AND** its severity does not override that exclusion

#### Scenario: Threshold is changed

- **WHEN** the recorded threshold is changed so that a previously excluded finding becomes
  eligible
- **THEN** that finding is submitted for triage on the next run
- **AND** verdicts already recorded against other findings are unaffected

### Requirement: Triage is invoked deliberately

The system SHALL publish scan findings automatically whenever infrastructure code
changes, and SHALL assign verdicts only when triage is explicitly invoked.

A code change SHALL NOT by itself cause verdicts to be assigned or tracker items to be
created.

#### Scenario: Infrastructure code changes

- **WHEN** a pull request modifies a `.tf` file
- **THEN** the scan runs and alert state is updated
- **AND** no verdict is assigned and no tracker item is created

#### Scenario: Triage is invoked

- **WHEN** triage is explicitly invoked
- **THEN** every eligible finding then present is triaged
- **AND** the findings triaged are those eligible at the time of invocation, not at the
  time of the last code change

### Requirement: Every triaged finding receives a verdict with a rationale

The system SHALL assign each finding submitted for triage exactly one verdict from a fixed
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
a tracker item for every triaged finding, whatever its verdict.

Each tracker item SHALL carry the verdict and its rationale in a form a human can read
without consulting alert state, and SHALL be identified by the finding's stable
identifier.

Tracker items SHALL be created under the label denoting work awaiting human evaluation,
using this repository's established triage label vocabulary. Deciding a finding's
disposition — that it is ready for an unattended agent, requires a human, or will not be
actioned — SHALL be a human act performed on the tracker item.

The system SHALL NOT itself apply the label denoting work ready for an unattended agent.

#### Scenario: Finding triaged with any verdict

- **WHEN** a finding is triaged and a verdict with a rationale is recorded
- **THEN** a tracker item is created for it carrying that verdict and rationale
- **AND** the item carries the label denoting work awaiting human evaluation

#### Scenario: Agent judges a finding ready for unattended work

- **WHEN** a finding's verdict is real with a mechanical fix
- **THEN** the verdict is stated on the tracker item as a proposal
- **AND** the label denoting work ready for an unattended agent is not applied by the
  system

#### Scenario: Human accepts a proposed verdict

- **WHEN** a human applies a disposition label to a tracker item
- **THEN** that label, not the recorded verdict, determines what happens to the item next

#### Scenario: Finding judged not applicable

- **WHEN** a finding's verdict is not applicable or accepted risk
- **THEN** a tracker item is still created stating that verdict and its rationale
- **AND** the alert is closed only where autonomous dismissal has been earned for that
  finding's rule

#### Scenario: Finding already has a tracker item

- **WHEN** a finding that already has an open tracker item is triaged again
- **THEN** no duplicate tracker item is created
- **AND** any human-applied disposition label on the existing item is left unchanged

### Requirement: Triage accuracy is measured against a fixed corpus

The system SHALL maintain a set of human-assigned verdicts covering the triage-eligible
findings present when this capability was introduced, and SHALL support scoring automated
verdicts against that set, reporting agreement per rule.

The corpus SHALL cover exactly the findings the system submits for triage. A finding
excluded by ownership or by the severity threshold SHALL NOT carry a human-assigned
verdict, and SHALL NOT contribute to any agreement figure.

The human-assigned verdicts SHALL be derived from triage decisions recorded against alert
state, rather than assigned in a separate store maintained alongside it, and SHALL be
recorded before any automated verdict exists.

Reported agreement figures SHALL be accompanied by the number of findings they are
computed over, per rule.

#### Scenario: Scoring a triage run

- **WHEN** automated verdicts are scored against the human-assigned set
- **THEN** agreement is reported broken down by rule
- **AND** each figure is reported alongside the number of findings it covers

#### Scenario: Human verdicts are recorded

- **WHEN** a human triages a finding
- **THEN** the verdict and its rationale are recorded against the finding's alert state
- **AND** the human-assigned corpus is derived from that state rather than authored
  separately

#### Scenario: A new rule produces findings absent from the corpus

- **WHEN** a finding arises from a rule with no human-assigned verdict
- **THEN** it is excluded from agreement figures rather than counted as agreement
- **AND** it is flagged as needing a human verdict

### Requirement: Autonomous dismissal is earned per rule

The system SHALL NOT close a finding's alert without human action unless automated
verdicts for that finding's rule have been scored against the human-assigned corpus, have
agreed on every case, and have been scored over at least a configured minimum number of
findings for that rule.

The minimum SHALL be greater than one, so that full agreement over a single case never
confers this authority.

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

#### Scenario: Rule agreed on every case but scored over too few

- **WHEN** a finding arises from a rule whose automated verdicts agreed on every scored
  case, but the number of scored findings for that rule is below the configured minimum
- **THEN** the verdict is presented for a human to apply
- **AND** the alert state is left unchanged

#### Scenario: Rule granted autonomous dismissal

- **WHEN** a finding arises from a rule that has been scored at full agreement over at
  least the configured minimum number of findings and explicitly granted authority
- **AND** its verdict is not applicable or accepted risk
- **THEN** its alert is closed automatically with the rationale recorded
- **AND** the closure remains visible and reversible

### Requirement: The pipeline degrades rather than fails

The system SHALL continue to report scan findings when the triage step cannot run.

#### Scenario: Inference is unavailable

- **WHEN** the triage step cannot run because model access is unavailable or fails
- **THEN** scan findings are still published as alert state
- **AND** the affected findings are left untriaged rather than being closed or discarded
