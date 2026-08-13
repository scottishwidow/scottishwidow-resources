# Self-hosted GitLab on AWS — design draft

Status: **draft, no code written**. Output of a `/grill-with-docs` session on
2026-08-13. Records the decisions reached, the facts they rest on, and the
sources. The next agent should read this before touching `live/gitlab/`.

Goal: an **educational but production-faithful** GitLab deployment. Topology
fidelity matters; instance sizes do not. No AIO/all-in-one shortcuts, no
Kubernetes.

## Shape of the thing

A downsized **2k reference architecture**, with AWS managed services
substituted for the self-managed Postgres and Redis nodes.

```
                    Route 53 (zone owned by live/management)
                              │
                         ACM cert
                              │
                    ┌─────────▼─────────┐
                    │       NLB         │  :443 TLS→:80, :22 TCP, :5050 registry
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         ┌────▼────┐     ┌────▼────┐          │
         │ Rails 1 │     │ Rails 2 │          │      t3.large
         └────┬────┘     └────┬────┘          │
              └───────┬───────┘               │
                      │                  ┌────▼─────┐
                      │                  │ Sidekiq  │  t3.medium
                      │                  └────┬─────┘
                      └───────┬────────────────┘
                              │
              ┌───────────────┼───────────────┬──────────────┐
              │               │               │              │
        ┌─────▼─────┐   ┌─────▼──────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │  Gitaly   │   │    RDS     │  │ElastiCache│  │    S3     │
        │ t3.medium │   │db.t4g.med  │  │ Valkey7.2 │  │ 11 buckets│
        │ + gp3 vol │   │ single-AZ  │  │t4g.micro  │  │           │
        └───────────┘   └────────────┘  └───────────┘  └───────────┘
```

EC2 fleet: Rails ×2, Sidekiq ×1, Gitaly ×1. No monitoring node, no HAProxy
node, no PgBouncer, no Consul, no Praefect.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Downsized **2k RA topology** with managed AWS services, not 1k, not 3k | Topology fidelity is the educational payload; a 1k monolith teaches nothing beyond "install Omnibus", 3k adds Patroni/Consul/Sentinel/Praefect plumbing that would never be operated here |
| 2 | **Write our own module**; GET is reference material only | GET is cloud-portable and assumes its own end-to-end Ansible; it fits badly with this repo's `modules/` + `live/` grain and ADR-0001 |
| 3 | **`gitlab-ee` unlicensed** (Free tier) | Same cost as CE, upgrade-in-place to Premium later, and what the RAs assume |
| 4 | New **`live/gitlab/`** environment, own state file | Blast-radius separation from Nextcloud/Song Vault |
| 5 | **Ansible over SSM** for config, not `user_data` | `gitlab.rb` is too large and too often-edited for `user_data`; `user_data` edits force instance replacement, catastrophic for the Gitaly node. Consistent with ADR-0001 |
| 6 | **amd64**, not Graviton | Every RA, every GET reference and most troubleshooting material is amd64. arm64 is supported but carries a "known issues" footnote |
| 7 | **Existing state bucket, new key** `gitlab/terraform.tfstate` | The state file is the blast-radius boundary, not the bucket |
| 8 | **One NLB**; ACM cert, TLS terminated at the LB | ALB cannot carry port 22 and Git-over-SSH is not optional. Kills all cert-renewal ops. Requires `proxied_ssl` / `real_ip` config in `gitlab.rb` |
| 9 | Route 53 zone **imported into `live/management`**; `live/gitlab/` looks it up via `data "aws_route53_zone"` by name and owns only its own records | Closes issue #20 where ownership belongs. Data source over `terraform_remote_state` per the vendored skill's rule (`module-patterns.md:205,259`) — a zone has an addressable name, so remote state buys nothing but coupling |
| 10 | Gitaly repos on a **separate encrypted gp3 volume**, root disk for OS only | The node can be replaced without touching repositories, and storage grows independently. Repos cannot go to S3 or EFS |
| 11 | **Container Registry in scope**, behind `enable_registry` (default on), on its own **port 5050** rather than 443 on `registry.<domain>` | Doing it later means revisiting DNS, cert and LB simultaneously. The port is forced by the LB choice: an NLB TLS listener can serve multiple certificates via SNI but routes all of them to a single target group, so it cannot send `registry.<domain>:443` and `gitlab.<domain>:443` to different backend ports on the same Rails nodes. A distinct listener port is the only way to keep one NLB |
| 12 | **Runners out of scope for v1**; follow-up `modules/gitlab_runner` | Separate lifecycle (autoscaling, spot, fleeting) and a different IAM story. In scope now: registration token in the secret store, and an SG rule for a future runner subnet |
| 13 | **`gitlab-secrets.json` in SSM Parameter Store** — seeded on first install, read on subsequent runs | Not covered by `gitlab-backup`. Lose it and every stored CI variable and 2FA secret becomes unreadable after a Rails node replacement |
| 14 | RDS **master credentials RDS-managed in Secrets Manager**; separate Secrets Manager secret for the GitLab app role; ephemeral / write-only values throughout | `manage_master_user_password` rotates every 7 days, so GitLab must not connect as master. Requires `required_version >= 1.11` |
| 15 | **Ansible creates the `gitlab` Postgres role**, not Terraform | The `cyrilgdn/postgresql` provider would require the Terraform runner to reach private-subnet RDS. Ansible already runs inside the VPC over SSM. Terraform creates the empty secret; Terraform never touches the database |
| 16 | RDS **single-AZ, no read replica, no PgBouncer**, `gp3`, automated backups 7d, deletion protection — behind a variable | Multi-AZ behind a single Sidekiq node is incoherent. One-line flip is the educational content |
| 17 | ElastiCache **Valkey 7.2, one non-clustered node**, `cache.t4g.micro` | Redis Cluster mode is unsupported. Three-way split (GET's shape) only earns its cost under eviction pressure. **Must use `noeviction`** on a single shared instance or Sidekiq loses jobs |
| 18 | **Ubuntu 24.04 LTS**, AMI pinned to an explicit ID | GET's default and the best-trodden path. A floating `most_recent = true` silently rebuilds Gitaly on an unrelated apply |
| 19 | **Backups: both layers.** `gitlab-backup create` → backups bucket as the restore path; RDS automated backups + DLM on the Gitaly volume + S3 versioning as the floor | Only the native backup gives a coherent cross-store restore, but it excludes secrets and does not re-copy blobs already in S3 |
| 20 | **CloudWatch agent + Logs**, three alarms: Gitaly disk-free, RDS free storage, NLB unhealthy hosts | Disk-full on Gitaly is *the* way self-hosted GitLab dies, and it is unrecoverable remotely once it happens |
| 21 | **Exact `gitlab-ee` package version pin** in an Ansible variable | Data outlives nodes: a replaced node installing "latest" can land on a version incompatible with the Gitaly volume and RDS it is about to mount. Required stops make this worse |
| 22 | **Terraform CI out of scope** for now | Explicitly deferred |
| 23 | Module decomposition: narrow modules composed in `live/gitlab/` | Matches repo grain. A shared `gitlab_node` primitive (GET's `gitlab_aws_instance` shape) contains the per-role variable explosion inside one small module |

Planned modules: `modules/gitlab_node` (the primitive), `modules/gitlab_object_storage`,
`modules/gitlab_database`, `modules/gitlab_lb`. Reuse `modules/vpc` and `modules/dlm_backup`.

## Hard constraints (violate these and it breaks)

- **Aurora is incompatible and unsupported.** RDS Proxy is not validated.
- **Redis Cluster mode is unsupported.** Standalone or Sentinel only.
- **Amazon RDS requires the `rds_superuser` role** for the GitLab database user.
- **Git repositories cannot live on S3 or EFS.** Gitaly needs local block storage.
  GitLab explicitly warns EFS "can negatively impact the performance of GitLab".
- **`gitlab-backup create` excludes `/etc/gitlab/gitlab-secrets.json` and
  `gitlab.rb`** — by design. It also does not back up blobs already in object storage.
- **Disk snapshots require read-only mode** to be consistent.
- **Upgrades have required stops** — since 17.5, at `x.2.z`, `x.5.z`, `x.8.z`, `x.11.z`.
  Current major is 19 (stops 19.2, 19.5, 19.8, 19.11).
- **`manage_master_user_password` cannot coexist** with `password` or `password_wo`.
- **Write-only arguments need Terraform 1.11+**; ephemeral resources need 1.10+.
  This repo currently pins `>= 1.0` (`live/management/versions.tf:2`).

## Consequence to carry forward

Splitting state across RDS + Gitaly volume + S3 **breaks the atomic-snapshot
property** that `live/management/CONTEXT.md` and ADR-0003 rely on for Nextcloud.
There, one EBS snapshot captures database and files at the same instant. Here it
cannot. That is why decision 19 needs both layers, and why the backup ADR must
say so explicitly.

## Object storage buckets

GET's default set, 11 buckets — worth mirroring:
`artifacts, backups, dependency-proxy, lfs, mr-diffs, packages, terraform-state,
uploads, registry, ci-secure-files, pages`.

Use **consolidated object storage configuration** with `use_iam_profile: true` —
no static access keys.

## Owed artifacts

ADRs — **written**:

- [ADR-0004](../adr/0004-gitlab-downsized-2k-reference-architecture.md) — topology:
  downsized 2k RA with managed AWS services; why not 1k, why not 3k.
- [ADR-0005](../adr/0005-gitlab-backup-strategy.md) — backups: native backup as restore
  path, infrastructure snapshots as floor; the loss of ADR-0003's atomic-snapshot premise.
- [ADR-0006](../adr/0006-gitlab-secrets-architecture.md) — secrets: RDS-managed master
  credentials plus a separate app role; `gitlab-secrets.json` in Parameter Store as what
  makes node replacement survivable.

Deliberately *not* ADRs: NLB-over-ALB (follows from port 22), Ubuntu 24.04
(reversible), amd64 (reversible), Rails ×2 (follows from the topology ADR).

Docs — **done**: `live/gitlab/CONTEXT.md`, `CONTEXT-MAP.md`.

Still owed:

- Amendment to `live/management/CONTEXT.md` once the Route 53 zone import lands — its
  manual `UPSERT` block stops being true.
- Repo-wide bump of `required_version` to `>= 1.11` (ADR-0006 depends on it).
- Runbooks: GitLab upgrade (encoding the required-stop rule and the Rails-node ordering),
  and GitLab restore. Until the restore runbook exists and has been exercised, ADR-0005 is
  a backup strategy on paper.

## Sources

### GitLab — architecture

- [Reference architectures index](https://docs.gitlab.com/administration/reference_architectures/) — selection guidance, unsupported configurations, GET/GPT tooling
- [1k RA (20 RPS)](https://docs.gitlab.com/administration/reference_architectures/1k_users/) — single node, 8 vCPU/16 GB (`c5.2xlarge`), no HA
- [2k RA (40 RPS)](https://docs.gitlab.com/administration/reference_architectures/2k_users/) — **our topology reference**; object storage required, still no HA
- [3k RA (60 RPS)](https://docs.gitlab.com/administration/reference_architectures/3k_users/) — first HA architecture; consulted, not adopted
- [GitLab architecture overview](https://docs.gitlab.com/development/architecture/) — component map

### GitLab — installation and platform

- [Install using the Linux package](https://docs.gitlab.com/install/package/)
- [Install on Ubuntu](https://docs.gitlab.com/install/package/ubuntu/)
- [Supported operating systems](https://docs.gitlab.com/administration/package_information/supported_os/) — arm64 support matrix and the "known issues on ARM" footnote
- [Installing a GitLab POC on AWS](https://docs.gitlab.com/install/aws/) — **POC only, not production**; EFS warning, single-Gitaly SPOF warning

### GitLab — external services

- [External PostgreSQL](https://docs.gitlab.com/administration/postgresql/external/) — `rds_superuser` requirement, extension installation
- [External Redis](https://docs.gitlab.com/administration/redis/replication_and_failover_external/) — ElastiCache/Valkey 7.2, no Cluster mode
- [Object storage](https://docs.gitlab.com/administration/object_storage/) — consolidated config, `use_iam_profile`, what can and cannot leave local disk
- [Load balancer](https://docs.gitlab.com/administration/load_balancer/) — ports 80/443/22, SSL termination options, `/-/readiness`

### GitLab — operations

- [Backup and restore](https://docs.gitlab.com/administration/backup_restore/)
- [Back up GitLab](https://docs.gitlab.com/administration/backup_restore/backup_gitlab/) — coverage/exclusions, S3 upload via IAM profile, snapshot caveats
- [Upgrade paths](https://docs.gitlab.com/update/upgrade_paths/) — required stops

### GitLab Environment Toolkit (reference implementation)

- [GET repository](https://gitlab.com/gitlab-org/gitlab-environment-toolkit) — "opinionated Terraform and Ansible scripts to assist with deploying scaled GitLab environments"
- AWS RA module: `terraform/modules/gitlab_ref_arch_aws/` — read `storage.tf`,
  `rds.tf`, `elasticache.tf`, `network.tf`, `gitaly.tf`, `elb_internal.tf`
- Instance primitive: `terraform/modules/gitlab_aws_instance/`
- Ansible roles: `ansible/roles/` — source for `gitlab.rb` content and secrets handling

Notable GET findings: it provisions **no managed external load balancer** — an
internal NLB (`aws_lb.gitlab_internal_lb`) plus a self-managed HAProxy EC2 node,
because GET must stay cloud-portable. We are not portable, so we use an NLB directly.

### AWS / Terraform

- [`aws_db_instance`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance) — `manage_master_user_password`, `password_wo`, `password_wo_version`
- [RDS password management with Secrets Manager](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html) — 7-day default rotation
- [Terraform write-only arguments](https://developer.hashicorp.com/terraform/language/manage-sensitive-data/write-only)
- Vendored `terraform-skill`: `.agents/skills/terraform-skill/references/` —
  `module-patterns.md` (remote-state rules), `security-compliance.md` (secrets),
  `code-patterns.md` (ephemeral / write-only)
