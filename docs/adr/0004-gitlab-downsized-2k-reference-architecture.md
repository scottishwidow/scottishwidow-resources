# 4. Host GitLab as a downsized 2k reference architecture with managed AWS services

Date: 2026-08-13

## Status

Accepted

## Context

We want a self-hosted GitLab in its own AWS environment (`live/gitlab`), built from
scratch with Terraform — no all-in-one appliance, no Kubernetes. The purpose is
explicitly **educational**: the value is in operating a realistic GitLab, not in
serving load. Actual demand is one user and a rounding error of requests per second.

That creates a tension that has to be resolved deliberately, because the two obvious
readings of "realistic" point in opposite directions.

GitLab publishes [reference architectures](https://docs.gitlab.com/administration/reference_architectures/)
sized in requests per second. The relevant ones:

- **[1k / 20 RPS](https://docs.gitlab.com/administration/reference_architectures/1k_users/)** —
  a single `c5.2xlarge` (8 vCPU, 16 GB) running Rails, Gitaly, Postgres, Redis, Sidekiq
  and Prometheus together. No HA.
- **[2k / 40 RPS](https://docs.gitlab.com/administration/reference_architectures/2k_users/)** —
  services split across nodes (LB, Postgres, Redis, Gitaly, Sidekiq, Rails ×2,
  monitoring). Object storage becomes **required**. Still no HA.
- **[3k / 60 RPS](https://docs.gitlab.com/administration/reference_architectures/3k_users/)** —
  the first genuinely highly-available architecture: Consul, PgBouncer, Patroni,
  Redis Sentinel, Praefect.

Sized honestly against demand, the answer is the 1k architecture, or something smaller
still. But a single box running everything is precisely what we already have for
Nextcloud (see [ADR-0002](0002-self-host-nextcloud-on-t4g-small.md)) — Terraform for one
EC2 instance teaches nothing new, and a single-node GitLab hides every problem worth
learning: shared state between web nodes, object storage, load balancer configuration,
secrets that must survive node replacement.

The decisive observation is that **topology fidelity and instance sizing are independent
axes**. The instructive content lives entirely in the topology. The instance sizes are
just money.

GitLab publishes its own Terraform + Ansible implementation, the
[GitLab Environment Toolkit](https://gitlab.com/gitlab-org/gitlab-environment-toolkit)
(GET), which builds these architectures directly.

## Decision

Deploy the **2k reference architecture topology, deliberately undersized**, with AWS
managed services substituted for the self-managed stateful nodes.

EC2 fleet — **Rails ×2** (`t3.large`), **Sidekiq ×1** (`t3.medium`), **Gitaly ×1**
(`t3.medium` plus a separate gp3 repository volume). Ubuntu 24.04 LTS, amd64,
`gitlab-ee` unlicensed (Free tier), AMI pinned to an explicit ID.

Substitutions from the published 2k architecture:

- Postgres node → **RDS**, single-AZ, `db.t4g.medium`, no read replica, no PgBouncer.
- Redis node → **ElastiCache for Valkey 7.2**, one non-clustered node, `cache.t4g.micro`.
- Local storage → **S3**, eleven buckets under GitLab's consolidated object storage
  configuration, reached by instance profile.
- Load balancer node → a single **NLB** with an ACM certificate.
- Monitoring node → **dropped**; CloudWatch agent and three alarms instead.

**Rails ×2 is the load-bearing part of this decision.** A single Rails node would let
broken shared-state configuration pass silently — it is the second node that forces
object storage, the shared secrets file and the load balancer to actually be correct.

Considered and rejected:

- **The 1k architecture (single node).** Correctly sized for real demand, but
  architecturally identical to the Nextcloud instance we already run. It would not
  exercise object storage, the load balancer, or shared secrets — the entire reason for
  doing this.
- **The 3k architecture (true HA).** The honest answer for a company. Patroni, Consul,
  Redis Sentinel and Praefect are a large amount of module surface for machinery that
  would never be operated here, and much of it is plumbing GET already solves generically.
  HA is explicitly declined; see the consequences below.
- **Self-managed Postgres and Redis on EC2**, as the published architecture specifies.
  Rejected because substituting managed services is what an AWS shop actually does, and
  because operating Patroni-less standalone Postgres on EC2 is a worse teacher than
  operating RDS. Note this is a *substitution*, not a simplification: it introduces the
  credential-rotation problem recorded in [ADR-0006](0006-gitlab-secrets-architecture.md).
- **Adopting GET wholesale.** GET is built for multi-node scaled environments and assumes
  its own Ansible layer end to end. It is cloud-portable by design, which is why it ships
  a self-managed HAProxy node and an internal NLB rather than using a managed load
  balancer — a constraint we do not share. It also fits badly against this repo's
  `modules/` + `live/` grain and [ADR-0001](0001-ansible-over-ssm.md)'s SSM transport. We
  write our own modules and treat GET and the reference architectures as the spec.
- **Graviton / arm64.** Supported for `gitlab-ee` on Ubuntu 24.04 since 17.1, and the
  house habit elsewhere in this repo (`t4g`). Rejected for v1 because every reference
  architecture, all of GET, and most troubleshooting material is amd64, and GitLab's
  support matrix carries a standing "known issues exist for running GitLab on ARM"
  footnote. Reversible later.

## Consequences

- **This is not a highly-available deployment**, despite having two Rails nodes. Gitaly,
  Sidekiq, RDS and ElastiCache are all single points of failure. Two Rails nodes buy
  correctness-forcing, not uptime. Do not read the topology as HA.
- RDS single-AZ is deliberate and coherent with the above: a Multi-AZ database behind a
  single Sidekiq node would double the bill to buy availability the application tier does
  not have. It is a variable, so flipping it is a one-line change — that flip is itself
  part of the educational content.
- **One shared Valkey instance must be configured `noeviction`.** GitLab supports splitting
  Redis by queue type, and GET provisions three parameter groups accordingly — `allkeys-lru`
  for the cache instance, `noeviction` for the shared and persistent ones. With a single
  instance serving all of them, `allkeys-lru` would evict Sidekiq's queues and silently
  lose background jobs.
- Instance sizes are undersized against the published architecture and use burstable
  instances. Sustained CI load will exhaust CPU credits. `t3.large` for Rails rather than
  `t3.medium` is not arbitrary — Puma is memory-bound and will OOM at 4 GB.
- Object storage is not optional at this topology, and the eleven-bucket layout mirrors
  GET's defaults: `artifacts, backups, dependency-proxy, lfs, mr-diffs, packages,
  terraform-state, uploads, registry, ci-secure-files, pages`.
- **Git repositories cannot be moved off the Gitaly node.** They require local block
  storage — not S3, and not EFS, which GitLab warns "can negatively impact the performance
  of GitLab". This constrains every later scaling or backup decision.
- CI runners are out of scope for this architecture and get their own module later. In
  scope now: a registration token in the secret store and a security-group rule for a
  future runner subnet.
