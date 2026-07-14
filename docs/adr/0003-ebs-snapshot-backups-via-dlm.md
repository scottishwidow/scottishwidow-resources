# 3. Back up Nextcloud with EBS snapshots via Data Lifecycle Manager

Date: 2026-07-14

## Status

Accepted

## Context

The Nextcloud instance (see [ADR-0002](0002-self-host-nextcloud-on-t4g-small.md)) had
**no backup of any kind** — no snapshots, no dumps, nothing. A bad AIO upgrade, a corrupt
disk, or a mistaken delete would have been unrecoverable. Nextcloud AIO ships a native
BorgBackup feature; we explicitly do not want it (it is configured through the AIO admin
UI, is opaque to Terraform, and stores backups on the same box unless given a remote).

The decisive fact about this instance is that **all of its state lives on one volume**.
Nextcloud splits its data in two: file blobs sit on the filesystem, while Postgres holds
the metadata describing them (`oc_filecache`, users, shares, trash). Neither half is a
backup on its own — a restore that pairs one with a differently-timed copy of the other
produces a Nextcloud that disagrees with its own disk. Both halves live in Docker volumes
under `/var/lib/docker/volumes` on the single 30 GB gp3 root volume. There is no separate
data volume.

Because it is *one* volume, a single EBS snapshot is **atomic**: it captures the database
and the file blobs at the same instant, coherently. That coherence is the property that
makes a Nextcloud backup restorable, and here we get it for free.

## Decision

Nightly **EBS snapshots** of the whole instance, driven by **AWS Data Lifecycle Manager**,
on a **7 daily / 4 weekly / 6 monthly** retention ladder in a single region
(`eu-central-1`). Roughly **€3–6/month**. Implemented as a reusable `modules/dlm_backup`
module — an IAM service role plus one `aws_dlm_lifecycle_policy` — called from
`live/management/main.tf` as `module.next_cloud_backup` and targeted by the tag
`Name=nextcloud`.

Alongside it, a `pg_dumpall` **escape hatch** (`nextcloud_pg_dump` Ansible role) writes a
gzipped logical dump to `/var/backups/nextcloud` on the root disk at 04:00 UTC, 30 minutes
before the snapshot, so the dump is captured *inside* the snapshot.

Considered and rejected:

- **AWS Backup.** DLM is free (pay only for snapshot storage), is ~40 lines of Terraform,
  and needs no vault/plan abstraction. AWS Backup's Vault Lock immutability is a worthwhile
  upgrade *if* snapshot deletion ever enters the threat model; it does not today.
- **Pre/post scripts (application-quiescing).** AWS ships **no** Linux app-consistent
  snapshot SSM document — only `AWSEC2-CreateVssSnapshot` for Windows VSS and the SAP HANA
  documents. Freezing the *root* filesystem is hazardous regardless: it can deadlock the
  very agent meant to thaw it. It is also unnecessary — the single-volume snapshot is
  already atomic, and Postgres WAL-replays on restore exactly as it would after a power cut.
  The policy therefore runs no scripts, and its IAM role carries no SSM permissions.
- **Cross-region copy.** Snapshots are already redundant across AZs within `eu-central-1`.
  Cross-region doubles cost to defend against a region loss we accept.
- **A separate data volume.** Splitting data off the root disk would *destroy* the
  atomicity above, requiring coordinated multi-volume snapshots to regain it.

## Consequences

- Snapshots are **crash-consistent, not application-quiesced**. Postgres replays its WAL on
  first start after a restore. This is the normal, supported recovery path.
- The `pg_dumpall` is **not a restore path** and must not be treated as one. Restoring a
  04:00 dump onto a 04:30 filesystem reintroduces precisely the skew the snapshot
  eliminates — files uploaded in that window exist on disk but are absent from
  `oc_filecache` (invisible to Nextcloud); files deleted in it are referenced by the
  database but gone from disk. It is for a corrupt Postgres cluster that will not
  WAL-replay, and its use requires `occ files:scan --all` to repair. See
  [the restore runbook](../runbooks/nextcloud-restore.md).
- The dump is written by Postgres **18**, so it can only be restored into an 18-or-newer
  cluster. A snapshot restore has no such constraint.
- Retention is bounded (7/4/6), so a corruption undetected for more than ~6 months is not
  recoverable. Acceptable for personal use.
- The DLM policy targets the tag `Name=nextcloud`. Anything else given that tag will also be
  snapshotted; conversely, if the instance is ever renamed, backups silently stop. The tag
  is the same one the Ansible dynamic inventory filters on, so a rename would break both
  loudly — but this coupling is worth remembering.
