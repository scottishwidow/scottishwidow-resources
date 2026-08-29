## Why

This repo provisions internet-facing AWS infrastructure (Nextcloud, Song Vault, and a
planned self-hosted GitLab) with no static security analysis at all. Nothing scans the
Terraform, and nothing decides what a finding means for *this* system.

The second half is the harder problem and the reason for doing this now. Scanners are
commodity; the bottleneck is triage. A first Trivy run over this repo produces 20
findings, of which 8 are in vendored registry modules we do not own and several more are
deliberate architecture decisions already recorded in `docs/adr/`. Raw scanner output is
therefore not actionable, and a suppression file discards the reasoning that justified
each suppression.

There is an active industry question — one being asked at the author's workplace — about
whether agentic triage can close that gap, and few non-proprietary implementations to
learn from. This change builds one on a real codebase, using only open components
(Trivy, GitHub code scanning, the MIT-licensed
[seclab-taskflow-agent](https://github.com/GitHubSecurityLab/seclab-taskflow-agent)), so
that the result is both a durable capability for this repo and a reference
implementation that transfers elsewhere.

## What Changes

- **Add a scanner.** Trivy `config` scanning over the Terraform in `live/` and
  `modules/`, emitting SARIF. Trivy only — Checkov was considered and dropped; a single
  scanner removes cross-tool deduplication entirely.
- **Add deterministic pre-classification.** Findings are partitioned into first-party
  (`live/`, `modules/`) and vendored (`.terraform/modules/`) before any model runs.
  Vendored findings are recorded as upstream and never sent for triage. On the current
  corpus this removes 40% of volume at zero inference cost.
- **Add a stable finding identity.** Trivy emits no `partialFingerprints`, so this
  change defines a fingerprint that survives line-number drift, without which every
  refactor re-triages everything.
- **Add agentic triage.** A `seclab-taskflow-agent` taskflow that fans out over
  first-party findings and assigns each a verdict, with the repo's ADRs and design docs
  supplied as context so that intentional decisions can be recognised as such.
- **Add a ground-truth fixture set.** All current findings hand-labelled once and
  committed, so agent output can be scored rather than merely inspected.
- **Route verdicts to existing sinks.** Findings land in GitHub code scanning (free on
  this public repo) as durable per-finding state; findings judged actionable are
  promoted to GitHub Issues using the label vocabulary already defined in
  `docs/agents/triage-labels.md`.
- **Gate agent autonomy on measured agreement.** The agent proposes verdicts and does
  not dismiss alerts on its own until per-rule agreement against the fixture set
  justifies it.

Explicitly **not** in this change: automated remediation; scanning of Ansible, shell, or
`user_data`; and plan-JSON scanning. Rationale for each is in `design.md`.

## Capabilities

### New Capabilities

- `iac-security-triage`: scanning this repo's infrastructure code, establishing a stable
  identity for each finding, classifying findings by ownership, assigning each
  first-party finding a triage verdict with recorded rationale, routing verdicts to
  code scanning and the issue tracker, and constraining how much of that the agent may
  do unsupervised.

### Modified Capabilities

None. This is the first capability recorded in `openspec/specs/`.

## Impact

- **New CI**: a workflow running Trivy and uploading SARIF to code scanning. Requires
  `security-events: write`. Runs on PRs and on `main`.
- **New AWS IAM**: an OIDC role for GitHub Actions is anticipated but **not needed by
  this change** — static HCL scanning requires no AWS credentials. The role becomes
  necessary only if plan-JSON scanning is adopted later.
- **New dependency**: `seclab-taskflow-agent` (Python 3.10+, MIT), run via its Docker
  image in CI. Requires an `AI_API_TOKEN` repository secret.
- **New repo content**: a taskflow definition, a triage personality, the normalisation
  step, and the committed ground-truth fixtures.
- **Existing docs become load-bearing**: `docs/agents/triage-labels.md` and
  `docs/agents/issue-tracker.md` move from convention to executable contract, and
  `docs/adr/` becomes agent input. ADR quality now affects triage quality.
- **Findings will be filed against `live/management/`**, which is live infrastructure.
  Triage output is advisory; no change applies itself.
- **`live/gitlab/` is unaffected for now** — it is design-only and contains no
  Terraform, so it produces no findings until it is built.
