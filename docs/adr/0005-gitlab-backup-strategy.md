# 5. Back up GitLab with native backups as the restore path and infrastructure snapshots as the floor

Date: 2026-08-13

## Status

Accepted

## Context

[ADR-0003](0003-ebs-snapshot-backups-via-dlm.md) backs up Nextcloud with a single nightly
EBS snapshot, and it works for one specific reason: **all of Nextcloud's state lives on
one volume**, so one snapshot captures database and file blobs at the same instant. That
ADR says so explicitly, and rejects a separate data volume precisely because it would
destroy that atomicity.

**That premise does not survive the GitLab architecture.** Under
[ADR-0004](0004-gitlab-downsized-2k-reference-architecture.md), GitLab's state is split
across three stores that cannot be captured at a single instant:

- **RDS** — the database.
- **The repository volume** — a separate encrypted gp3 volume on the Gitaly node,
  deliberately not the root disk so the node can be rebuilt without touching Git data.
  Repositories cannot live anywhere else; S3 and EFS are both excluded.
- **S3** — artifacts, LFS, uploads, MR diffs, packages, registry images, Pages.

Snapshotting all three independently produces three timestamps and no coherent moment.
A restore that pairs a database with a differently-timed set of repositories gives a
GitLab that disagrees with itself — the same class of failure ADR-0003 was designed to
avoid, reintroduced by the topology.

GitLab's own [backup tooling](https://docs.gitlab.com/administration/backup_restore/backup_gitlab/)
addresses this, but has sharp exclusions:

- It covers database, repositories, LFS, artifacts, packages, registry images, wikis,
  uploads, Pages, Terraform state and snippets.
- It **excludes `/etc/gitlab/gitlab-secrets.json` and `gitlab.rb`** — deliberately, because
  "storing encrypted information in the same location as its key defeats the purpose of
  using encryption".
- It **does not back up blobs already held in object storage**. At this topology, that is
  most of the data by volume.
- Disk snapshots are an accepted alternative, but **only with GitLab in read-only mode**
  for consistency.
- It can upload directly to S3 using an IAM instance profile.

## Decision

Run **both layers**, with distinct and non-interchangeable jobs.

**The restore path** — scheduled `gitlab-backup create`, uploaded to the `backups`
bucket via instance profile. This is the only artefact that reconstitutes database,
repositories and blobs as one coherent whole, and it is what an actual recovery uses.

**The floor** — RDS automated backups (7-day retention, deletion protection), DLM
snapshots of the repository volume via the existing `modules/dlm_backup`, and S3
versioning with a lifecycle policy on the object storage buckets. Each protects one
store independently. They are insurance against losing a store, not a recovery procedure.

**The secrets file is handled separately and is not part of either layer.**
`gitlab-secrets.json` is generated once and held in SSM Parameter Store — see
[ADR-0006](0006-gitlab-secrets-architecture.md). This is not an optimisation; without it
the native backup is unrestorable, because the backup contains ciphertext whose key was
never captured.

Considered and rejected:

- **Native backups only.** Cheaper and conceptually clean, but it does not re-copy blobs
  already in object storage, so a bucket deletion would be unrecoverable. It also has no
  answer for a corrupt backup discovered late.
- **Infrastructure snapshots only** (the ADR-0003 approach, extended to three stores).
  Rejected because three independent snapshot schedules cannot produce a consistent
  restore point, and coordinating them would require putting GitLab in read-only mode —
  at which point the native backup is strictly better.
- **Quiescing GitLab to take coherent multi-store snapshots.** Technically the way to
  restore atomicity, but it means scheduled read-only windows for a service that should
  just work, to produce something the native backup already gives without downtime.

## Consequences

- **ADR-0003's atomic-snapshot property is explicitly abandoned here.** Anyone reasoning
  about GitLab backups by analogy with Nextcloud will reach wrong conclusions. The two
  environments are backed up on different principles for a structural reason, not through
  inconsistency.
- **"Backup" is now ambiguous in this environment** and must always be qualified as either
  the *restore path* or the *floor*. `live/gitlab/CONTEXT.md` records both terms.
- **The floor cannot be combined into a restore.** Restoring an RDS snapshot alongside a
  volume snapshot taken minutes apart reproduces exactly the skew this ADR exists to
  document. Like ADR-0003's `pg_dumpall` escape hatch, the floor is for the case where the
  proper path is gone, and using it implies repair work afterwards.
- The native backup's usefulness depends entirely on the secrets file being preserved
  elsewhere. That dependency is load-bearing and is the subject of ADR-0006.
- S3 versioning protects against deletion and overwrite, not against a bucket-level
  disaster. Cross-region replication is available in GET and deliberately not adopted, on
  the same reasoning as ADR-0003: it doubles cost to defend against a region loss we accept.
- Restore has never been exercised. A restore runbook is owed, and until it exists this is
  a backup strategy on paper.
