# Context Map

## Contexts

- [Management](./live/management/CONTEXT.md) — the `management` AWS environment:
  the Nextcloud and Song Vault instances, their Terraform, and the Ansible that
  configures Nextcloud.
- [GitLab](./live/gitlab/CONTEXT.md) — the `gitlab` AWS environment: a self-hosted
  GitLab modelled on GitLab's 2k reference architecture, with RDS, ElastiCache and
  S3 in place of the self-managed Postgres, Redis and local storage. **Design only —
  nothing provisioned yet.** Start at [the design draft](./docs/design/gitlab-on-aws.md).

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
