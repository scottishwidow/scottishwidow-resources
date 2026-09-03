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
- **Add deterministic pre-classification, in two stages.** Findings are first
  partitioned into first-party (`live/`, `modules/`) and vendored
  (`.terraform/modules/`); vendored findings are recorded as upstream and never sent for
  triage. What survives is then gated on severity, and only `HIGH` and `CRITICAL`
  findings are triaged. Both stages run before any model does. Together they remove 13 of
  20 findings — 65% of volume — at zero inference cost.

  The two stages are not interchangeable and the order matters: every `CRITICAL` finding
  in this repo is vendored, so a severity gate applied alone would send the model the
  eight findings that can never be actioned here and drop five first-party ones.
- **Add a stable finding identity.** Trivy emits no `partialFingerprints`, so this
  change defines a readable composite key — rule, module address and resource address —
  that survives line-number drift, without which every refactor re-triages everything.
- **Add agentic triage, invoked on demand.** A `seclab-taskflow-agent` taskflow that
  fans out over the eligible findings and assigns each a verdict, with the repo's ADRs
  and design docs supplied as context so that intentional decisions can be recognised as
  such. Scanning stays automatic on every change; triage is started deliberately. The
  framework is a CLI with no event model of its own, so this is also its natural shape.
- **Add a ground-truth fixture set.** An export that harvests triage decisions from code
  scanning alert state into a committed fixture, plus schema validation and a scorer, so
  agent output can be scored rather than merely inspected. Labelling happens in the tool
  that holds the state rather than in a parallel file, and never extends beyond the set
  the agent triages. The ordering rule is what gives the corpus its value: a verdict is
  recorded before the agent has produced one, never after. This change ships the
  mechanism rather than a populated corpus — the original seven eligible findings were
  deliberately released to the agent untriaged (`design.md - Decision 5`, task 3.1), so
  population begins with the findings admitted by the next threshold drop.
- **Route verdicts to existing sinks.** All findings land in GitHub code scanning (free
  on this public repo) as durable per-finding state. Every *triaged* finding is
  additionally promoted to a GitHub Issue carrying the agent's verdict and rationale,
  because deciding whether a finding is worth acting on is the human judgment this
  pipeline exists to inform, not one the agent makes alone. Filing per finding is
  affordable precisely because the two deterministic filters reduce twenty findings to
  seven.

  The agent files issues under `needs-triage`; a human converts that to
  `ready-for-agent`, `ready-for-human` or `wontfix` from the vocabulary in
  `docs/agents/triage-labels.md`. The agent never applies `ready-for-agent` itself — that
  label authorises unattended work, and an agent that could apply it would be authorising
  itself.
- **Gate agent autonomy on measured agreement over a minimum number of cases.** The
  agent proposes verdicts and does not dismiss alerts on its own until a rule shows full
  agreement against the fixture set over enough findings to mean something. Eight of the
  ten first-party rules fire exactly once, so agreement alone is not a bar; on the current
  corpus no rule clears the floor and the allowlist is empty.

Explicitly **not** in this change: automated remediation; scanning of Ansible, shell, or
`user_data`; and plan-JSON scanning. Rationale for each is in `design.md`.

Remediation is a successor change rather than an omission. This change ends at a labelled
issue: a human applying `ready-for-agent` is the handoff point, and what consumes that
label is out of scope here. It also needs a different executor —
`seclab-taskflow-agent` ships read and analysis toolboxes and no ability to edit files or
open pull requests — so folding it in would mean carrying two unrelated agents under one
capability.

## Capabilities

### New Capabilities

- `iac-security-triage`: scanning this repo's infrastructure code, establishing a stable
  identity for each finding, classifying findings by ownership and severity to decide
  which are triaged at all, assigning each eligible finding a triage verdict with
  recorded rationale, routing verdicts to code scanning and the issue tracker, and
  constraining how much of that the agent may do unsupervised.

### Modified Capabilities

None. This is the first capability recorded in `openspec/specs/`.

## Impact

- **New CI**: a workflow running Trivy and uploading SARIF to code scanning. Requires
  `security-events: write`. Runs on PRs and on `main`. A second, manually dispatched
  workflow runs triage; it is never triggered by a push.
- **New AWS IAM**: an OIDC role for GitHub Actions is anticipated but **not needed by
  this change** — static HCL scanning requires no AWS credentials. The role becomes
  necessary only if plan-JSON scanning is adopted later.
- **New dependency**: `seclab-taskflow-agent` (Python 3.10+, MIT), run via its Docker
  image in CI. Requires an `AI_API_TOKEN` repository secret.
- **New repo content**: a taskflow definition, a triage personality, the normalisation
  step, the fixture export tool, and the committed ground-truth fixtures.
- **Existing docs become load-bearing**: `docs/agents/triage-labels.md` and
  `docs/agents/issue-tracker.md` move from convention to executable contract, and
  `docs/adr/` becomes agent input. ADR quality now affects triage quality.
- **Findings will be filed against `live/management/`**, which is live infrastructure.
  Triage output is advisory; no change applies itself.
- **The issue tracker gains roughly seven issues per full triage run**, deduplicated on
  finding key across runs. Below-threshold first-party findings remain visible as open
  code scanning alerts and produce no issues.
- **`live/gitlab/` is unaffected for now** — it is design-only and contains no
  Terraform, so it produces no findings until it is built.
