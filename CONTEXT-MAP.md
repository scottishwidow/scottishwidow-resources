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
  with a rationale, and bounds how much of that judgment happens without a human.
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
- **Triage → GitLab (the corpus)**: `live/gitlab/` is where the evaluation corpus
  becomes worth measuring. Today's is 9 findings over 8 rules, 7 of which fire
  exactly once — enough to validate the mechanism, not enough to support an
  accuracy claim. RDS, ElastiCache and load balancer findings are what widen it,
  and two deferred measurement tasks are waiting on exactly that.
- **ADRs, design docs → Triage**: `docs/adr/` and `docs/design/` are read into
  every triage prompt by `context.py` — a model with `ADR-0004` in context can
  know a permissive rule is intentional where a rule engine cannot. This is the
  pipeline's actual differentiator over a suppression file, and it means **a new
  ADR becomes triage context by existing**. It also means a design doc that named
  per-finding verdicts would hand the agent answers it is about to be scored
  against; don't write one.
