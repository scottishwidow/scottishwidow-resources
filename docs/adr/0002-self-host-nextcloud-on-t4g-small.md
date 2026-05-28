# 2. Self-host Nextcloud AIO on a t4g.small instance

Date: 2026-05-29

## Status

Accepted

## Context

Nextcloud AIO runs a multi-container stack (Apache, Nextcloud/PHP-FPM,
PostgreSQL, Redis, optional Imaginary/ClamAV/Talk/Collabora) and needs ~2 GB RAM
as a practical floor. The instance was defaulted to `t4g.nano` (0.5 GB), which
cannot run the stack — the child containers OOM during setup.

The alternative to self-hosting is a Nextcloud subscription. These split sharply:
Nextcloud GmbH's enterprise subscription is per-user/year with a large seat
minimum (~€1,500+/year), while budget managed hosts (e.g. Hetzner Storage Share)
start ~€5/month including ~1 TB.

## Decision

Self-host on AWS and size the instance at **`t4g.small` (2 GB RAM)** as the
practical floor for AIO. Estimated cost ~US$20/month on-demand in `eu-central-1`
(instance + 30 GB gp3 + public IPv4), ~US$13–14/month with a 1-year Compute
Savings Plan.

Required Terraform changes (to be made during implementation):
- `next_cloud_instance_type` default → `t4g.small`.
- Explicit root volume size (~30 GB gp3) on the `ec2-instance` module, since the
  AMI default is too small for container images + data + Postgres.

## Consequences

- Far cheaper than the enterprise subscription; **more expensive** than budget
  managed hosting (~€5/mo for ~1 TB) — we accept the higher cost and the ops
  burden in exchange for control.
- If files grow, the gp3 volume must be grown (or a separate data volume added);
  RAM may need a further bump for Collabora/Talk/ClamAV (→ `t4g.medium`).
