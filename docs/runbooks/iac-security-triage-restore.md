# Restore the IaC security triage pipeline

The IaC security triage and remediation pipeline was a proof of concept. It
worked, and it is archived: its code, its three workflows and its as-built
design are removed from `main` and held at the annotated tag
**`poc/iac-security-triage`** (commit `7f6856a`). This runbook brings it back.

## What is archived

    security/iac_security/                          the whole capability
    .github/workflows/iac-security-triage.yml       the triage agent
    .github/workflows/iac-security-remediate.yml    the remediation agent
    .github/workflows/iac-security-reconcile.yml    alert dismissal on a wontfix close
    .github/workflows/tests.yml                     the two unittest suites
    docs/design/iac-security-triage.md              the as-built design

Read the design without restoring anything:

    git show poc/iac-security-triage:docs/design/iac-security-triage.md

## What stays on main

`.github/workflows/iac-security-scan.yml` still runs Trivy on every pull request
and every push to `main`, and still publishes SARIF to code scanning. Alerts are
therefore still raised; nothing triages them, files an issue for them, or
dismisses them while the pipeline is archived. That is the intended state.

## Restore

1. Take the files back onto a branch:

       git checkout -b restore/iac-security-triage
       git checkout poc/iac-security-triage -- \
         security/iac_security \
         .github/workflows/iac-security-triage.yml \
         .github/workflows/iac-security-remediate.yml \
         .github/workflows/iac-security-reconcile.yml \
         .github/workflows/tests.yml \
         docs/design/iac-security-triage.md

2. Run both suites. They are offline: no Trivy, no AWS, no Docker, no model
   token, no network, no Terraform.

       python3 -m pip install pyyaml
       python3 -m unittest discover -s security/iac_security/tests
       python3 -m unittest discover -s security/iac_security/taskflow/tests

   `test_workflows.py` asserts about the workflow YAML, so it fails first and
   loudest if a workflow file was left behind.

3. Restore the pointers this archive rewrote: the context map entry in
   `CONTEXT-MAP.md` and the `ready-for-remediation` paragraph in
   `docs/agents/triage-labels.md`. Both name this runbook, so search for it.

4. Merge the branch. The workflow files are new to `main` again, so GitHub
   registers them as **active** — the `disabled_manually` state they carried
   before the archive is gone with the files, and nothing needs re-enabling.

## Prerequisites on GitHub

- **Secret `AI_API_TOKEN`** — the Anthropic API key both agents authenticate
  with. It is the only credential the pipeline holds; the archive does not
  preserve it, so set it again.
- **Label `ready-for-remediation`** — the label a human applies to ask for a
  patch. The remediation workflow triggers on it and on nothing else.
- **Code scanning enabled**, so the scan's SARIF lands as alerts and
  reconciliation has an alert to dismiss.
- **Actions permitted to create pull requests**, for the patch the remediation
  workflow opens.

## Before you restore

The pipeline reads the whole first-party Terraform corpus into each agent
prompt. That arithmetic held at 24 files and roughly 6k tokens per finding. If the
corpus has grown since, read
[ADR-0008](../adr/0008-this-repository-is-not-a-memory-bank.md) first: at about
ten times that size, the corpus stops being something to push and a pull-based
read toolbox becomes the right shape.
