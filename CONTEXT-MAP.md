# Context Map

## Contexts

- [Management](./live/management/CONTEXT.md) — the `management` AWS environment:
  the Nextcloud and Song Vault instances, their Terraform, and the Ansible that
  configures Nextcloud.
- [GitLab](./live/gitlab/CONTEXT.md) — the `gitlab` AWS environment: a self-hosted
  GitLab modelled on GitLab's 2k reference architecture, with RDS, ElastiCache and
  S3 in place of the self-managed Postgres, Redis and local storage. **Design only —
  nothing provisioned yet.** Start at [the design draft](./docs/design/gitlab-on-aws.md).
- [IaC security triage](./security/iac-security-triage/CONTEXT.md) — the pipeline
  that scans the Terraform for misconfigurations, assigns each finding a verdict
  with a rationale, and proposes a patch where a human asks for one. Nothing
  merges and nothing is dismissed without a human ([ADR-0008](./docs/adr/0008-this-repository-is-not-a-memory-bank.md)).
  Spans no AWS environment and needs no cloud credentials. Start at [the as-built
  design](./docs/design/iac-security-triage.md).

## Relationships

- **Terraform → Ansible**: Terraform (`live/management/`) provisions the instance
  and supporting resources (EIP, Route 53 record, SSM scratch bucket); Ansible
  (`live/management/ansible/`) configures Nextcloud AIO on it, standalone (no
  `remote-exec`). They share no state file — Ansible discovers the instance via
  dynamic inventory (tags) and reads bucket/region from Terraform outputs.
- **Management → GitLab (DNS)**: the Route 53 hosted zone is to be imported into
  and owned by `live/management/` (issue #20). `live/gitlab/` resolves it with a
  `data "aws_route53_zone"` lookup by name — not `terraform_remote_state` — and
  manages only its own records. Once the import lands, the manual `UPSERT`
  procedure documented in `live/management/CONTEXT.md` is no longer accurate.
- **GitLab: Terraform → Ansible**: same split as management, and for the same
  reason — Terraform provisions nodes, volumes, RDS, ElastiCache, buckets and the
  load balancer; Ansible over SSM renders `gitlab.rb` per node role and creates the
  database app role from inside the VPC. `gitlab.rb` is deliberately *not* in
  `user_data`: `user_data` edits replace instances, which is intolerable for the
  Gitaly node.
- **Triage → Management, GitLab (reads only)**: the scanner reads every `.tf` file
  in the repo, so both environments are its input, but it provisions nothing and
  holds no AWS credentials — it reads *code*, never live infrastructure. Ownership
  is decided on the **owner path**, so a finding in `modules/` reached through
  `live/management/` is first-party and triaged, while one in `.terraform/modules/`
  is recorded upstream and never sent to a model.
- **Terraform → Triage (the corpus)**: every first-party `.tf` file in the repo is
  assembled into the **Terraform corpus** and carried in each agent's prompt, so
  the code — both environments' and every module's — is the whole of what an agent
  knows about this system. It is small enough to push: 24 files, ~20KB, ~6k tokens
  per finding. `live/gitlab/` landing is what changes that arithmetic, and at
  roughly ten times today's size a pull-based read toolbox becomes worth building
  ([ADR-0008](./docs/adr/0008-this-repository-is-not-a-memory-bank.md)).
- **ADRs, design docs → nothing**: they are *not* agent input, and the machinery
  that made them so is deleted. `docs/design/` is where development thinking is
  worked out and is half-formed by design; feeding it to an agent promoted drafts
  to facts. A new ADR changes what an agent sees only by changing the Terraform.
  This is the line ADR-0008 draws, and the corpus assembler is the one place it
  could be quietly crossed — it may contain code and never prose.
