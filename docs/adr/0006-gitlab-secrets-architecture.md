# 6. Split GitLab's database credentials from its application secrets, and keep both out of Terraform state

Date: 2026-08-13

## Status

Accepted

## Context

The GitLab environment ([ADR-0004](0004-gitlab-downsized-2k-reference-architecture.md))
has three distinct kinds of secret material, and treating them as one problem produces a
broken system in three different ways.

**1. Database credentials.** GitLab on RDS
[requires the `rds_superuser` role](https://docs.gitlab.com/administration/postgresql/external/)
for its database user. The obvious move — hand GitLab the RDS master credentials — collides
with `manage_master_user_password`, which has RDS generate the master password into Secrets
Manager and **rotate it every 7 days by default**. GitLab reads its database password from
`gitlab.rb` at reconfigure time; it would break on the first rotation. The AWS provider also
forbids combining `manage_master_user_password` with `password` or `password_wo`, so this is
not something to paper over.

Creating the application's own Postgres role needs a connection to the database. The
`cyrilgdn/postgresql` provider would require the Terraform runner to reach RDS — which,
sitting in private subnets, it cannot, and should not.

**2. The application secrets file.** `/etc/gitlab/gitlab-secrets.json` holds the keys that
encrypt stored CI variables, 2FA secrets and tokens. It is generated on first install, and
GitLab's backup tooling **deliberately excludes it**. Under ADR-0004 the durable state
(RDS, the repository volume) outlives every node, so a Rails node replacement with a freshly
generated secrets file yields a running GitLab whose stored CI variables and 2FA secrets are
permanently undecryptable. With two Rails nodes, the file must additionally be *identical*
across them.

**3. Everything else** — the initial root password, runner registration tokens.

Meanwhile, marking a Terraform variable `sensitive = true` masks display only; the value
still lives in state. Write-only arguments (`*_wo`, Terraform 1.11+) and ephemeral resources
(1.10+) are what actually keep material out of state. This repo currently pins
`required_version = ">= 1.0"`.

## Decision

Three stores, chosen by who owns the value and how it changes.

**RDS master credentials → RDS-managed, in Secrets Manager.** `manage_master_user_password
= true`. Rotation stays on. Nothing in Terraform ever reads them. They are used only to
administer the database.

**The GitLab application role → a separate Secrets Manager secret.** Terraform creates the
secret; the value is supplied through ephemeral/write-only arguments so it never reaches
state. **Ansible creates the matching Postgres role**, running inside the VPC over SSM
([ADR-0001](0001-ansible-over-ssm.md)), reading the master credentials from Secrets Manager
to authenticate and granting the new role `rds_superuser`. **Terraform never connects to the
database.**

**`gitlab-secrets.json` and application tokens → SSM Parameter Store (SecureString).**
Ansible reads the parameter on every run: if present, it is written to disk before
`gitlab-ctl reconfigure`; if absent, GitLab generates one and Ansible seeds it back. Both
Rails nodes therefore converge on the same file, and a rebuilt node rejoins with the keys
matching the data it is about to serve.

`required_version` is raised to **`>= 1.11`** across the repo, since write-only arguments
require it.

Considered and rejected:

- **GitLab connecting as the RDS master user.** Simplest, and wrong: password rotation
  breaks the application on a 7-day timer, and it discards least privilege for the one
  credential with unrestricted database access.
- **Disabling master password rotation** to make the above safe. Rejected — it trades a
  managed, rotating credential for a static one to avoid creating a single Postgres role.
- **Terraform creating the Postgres role** via `cyrilgdn/postgresql`. Requires network
  reachability from wherever Terraform runs to RDS, which means either running Terraform
  inside the VPC or exposing the database. Both are worse than letting Ansible — already
  inside the VPC by design — do it.
- **Secrets Manager for `gitlab-secrets.json` too**, for consistency. Rejected on cost and
  fit: Parameter Store SecureString is effectively free, the nodes already hold SSM
  permissions for the Ansible transport, and the file needs no rotation — rotating it would
  destroy the data it decrypts.
- **`secret.auto.tfvars` plus Ansible Vault**, the pattern used in `live/management`.
  Rejected because a gitignored tfvars file is not a store: it does not survive a lost
  workstation, cannot be read by a node at reconfigure time, and puts values into state
  anyway.

## Consequences

- **Losing the `gitlab-secrets.json` parameter is unrecoverable** in a way that losing a
  node is not. The backup ([ADR-0005](0005-gitlab-backup-strategy.md)) contains ciphertext
  whose key lives only here. This parameter is the single most valuable object in the
  environment and must never be deleted with the stack.
- The bootstrap has an ordering constraint that is easy to get wrong: the parameter is
  written only *after* the first successful install, so the first Ansible run and every
  subsequent one take different paths through the same role. That path must be idempotent
  and must be tested, not assumed.
- Terraform's plan cannot show what a secret value is or whether it changed — that is the
  point of write-only arguments, but it means drift in these values is invisible to
  `terraform plan` and must be reasoned about elsewhere.
- Raising `required_version` to `>= 1.11` affects `live/management` too. Bumping it
  repo-wide is deliberate: divergent Terraform version floors across environments in one
  repo is a worse problem than the bump.
- Ansible now needs IAM permission to read Secrets Manager and Parameter Store, widening
  the node instance roles beyond `AmazonSSMManagedInstanceCore`. ADR-0001's tightly-scoped
  role does not carry over unchanged to this environment.
- The database is reachable only from inside the VPC, and creating the application role is
  now a step in the Ansible run rather than in `terraform apply`. A fresh environment is not
  usable after `apply` alone — it requires the Ansible run to complete.
