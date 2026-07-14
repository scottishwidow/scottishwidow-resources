# Runbook: Nextcloud restore from an EBS snapshot

Recover the Nextcloud instance from a Data Lifecycle Manager snapshot after a bad AIO
upgrade, disk corruption, or a destructive mistake. Backups are described in
[ADR-0003](../adr/0003-ebs-snapshot-backups-via-dlm.md).

Unlike the [smoke test](nextcloud-smoke-test.md), this runbook **mutates production**. Read
the whole procedure before starting it.

There are two procedures. **Use the first one.** The second is a degraded escape hatch with
a real cost, spelled out below.

## Why the snapshot restore works

All Nextcloud state — the Postgres metadata *and* the file blobs — lives in Docker volumes
on the instance's single root volume. One snapshot therefore captures both at the same
instant. Restoring it gives you a coherent Nextcloud, not a database that disagrees with
its own disk. The snapshot is crash-consistent, not quiesced: Postgres replays its WAL on
first boot exactly as it would after a power cut. That is normal and expected.

## Prerequisites

- AWS credentials for account `975049889162`, region `eu-central-1`.
- The instance ID and its current root volume.

```sh
REGION=eu-central-1
IID=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Name,Values=nextcloud" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
```

## Step 1 — Pick the snapshot

```sh
aws ec2 describe-snapshots --region "$REGION" --owner-ids self \
  --filters "Name=tag:Name,Values=nextcloud-backup" \
  --query 'sort_by(Snapshots,&StartTime)[].{Id:SnapshotId,Started:StartTime,Sched:Tags[?Key==`Schedule`]|[0].Value,State:State,Size:VolumeSize}' \
  --output table
```

Choose the newest snapshot **from before the damage**. Note its ID.

```sh
SNAP=snap-xxxxxxxxxxxx
```

> **Restoring loses everything written after the snapshot.** If the instance is still
> serving, consider taking an ad-hoc snapshot of the *current* volume first — it is the only
> copy of the damaged state, and you may want it for forensics or partial recovery:
> `aws ec2 create-snapshots --region "$REGION" --instance-specification InstanceId="$IID" --description "pre-restore forensic"`

## Step 2 — Stop the instance

```sh
aws ec2 stop-instances --region "$REGION" --instance-ids "$IID"
aws ec2 wait instance-stopped --region "$REGION" --instance-ids "$IID"
```

The **Elastic IP and the Route 53 A record are untouched by this whole procedure**, so DNS
keeps working and the Let's Encrypt certificate survives the restore.

## Step 3 — Build a new volume from the snapshot

The volume must be in the **same availability zone** as the instance.

```sh
AZ=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$IID" \
  --query 'Reservations[0].Instances[0].Placement.AvailabilityZone' --output text)

NEWVOL=$(aws ec2 create-volume --region "$REGION" \
  --snapshot-id "$SNAP" --availability-zone "$AZ" \
  --volume-type gp3 --encrypted \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=nextcloud-restored}]' \
  --query VolumeId --output text)

aws ec2 wait volume-available --region "$REGION" --volume-ids "$NEWVOL"
```

## Step 4 — Swap the root volume

Capture the old volume ID **before** detaching — you will want it if the restore fails.

```sh
OLDVOL=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$IID" \
  --query 'Reservations[0].Instances[0].BlockDeviceMappings[?DeviceName==`/dev/sda1`].Ebs.VolumeId' \
  --output text)
echo "old root volume: $OLDVOL"

aws ec2 detach-volume --region "$REGION" --volume-id "$OLDVOL"
aws ec2 wait volume-available --region "$REGION" --volume-ids "$OLDVOL"

aws ec2 attach-volume --region "$REGION" \
  --volume-id "$NEWVOL" --instance-id "$IID" --device /dev/sda1
aws ec2 wait volume-in-use --region "$REGION" --volume-ids "$NEWVOL"
```

The root device is `/dev/sda1` — confirmed on the live instance. Attaching at any other
device name will not boot.

## Step 5 — Start and verify

```sh
aws ec2 start-instances --region "$REGION" --instance-ids "$IID"
aws ec2 wait instance-running --region "$REGION" --instance-ids "$IID"
```

Postgres will WAL-replay on first start; give the stack a couple of minutes to settle, then
**run the [smoke test](nextcloud-smoke-test.md) end to end**. The restore is not complete
until it passes: containers healthy, `occ status` installed and not in maintenance, and the
public domain serving `status.php` over valid TLS.

## Step 6 — Clean up

Once the smoke test passes and you are confident, delete the old volume. **Keep it until
then** — it is your only way back.

```sh
aws ec2 delete-volume --region "$REGION" --volume-id "$OLDVOL"
```

## Rollback (the restore itself failed)

Stop the instance, detach `$NEWVOL`, re-attach `$OLDVOL` at `/dev/sda1`, start. You are back
to the damaged-but-known state, having lost nothing.

---

# ⚠️ Escape hatch — restoring from the `pg_dumpall` (degraded)

**Do not use this as a restore path.** It exists for exactly one situation: the Postgres
cluster itself is corrupt and will not WAL-replay, so the snapshot's database is unusable
while its *files* are fine.

The dumps are written by the [`nextcloud_pg_dump`](../../live/management/ansible/roles/nextcloud_pg_dump/README.md)
role to `/var/backups/nextcloud/pg-YYYY-MM-DD.sql.gz` at 04:00 UTC — 30 minutes before the
04:30 snapshot, and therefore captured *inside* it.

## What it costs you

Nextcloud keeps file blobs on the filesystem and their metadata in Postgres. Pairing a
**04:00 dump** with a **04:30 filesystem** reintroduces exactly the skew the atomic snapshot
was there to eliminate:

- Files **uploaded** in that 30-minute window exist on disk but have no row in
  `oc_filecache` — Nextcloud cannot see them.
- Files **deleted** in that window are still referenced by the database but are gone from
  disk — Nextcloud shows entries that fail to open.

Nobody should reach for this path without knowing that.

## Procedure

1. Restore the snapshot as above (Steps 1–5). The filesystem is now good; the database is
   the problem.
2. Recreate the cluster from the dump. The dump is a `pg_dumpall`, so it restores the whole
   cluster including roles:

   ```sh
   # via SSM on the instance
   gzip -cd /var/backups/nextcloud/pg-YYYY-MM-DD.sql.gz \
     | docker exec -i nextcloud-aio-database sh -c 'psql -U "$POSTGRES_USER" -d postgres'
   ```

   The database user is read from the container's own environment (currently `nextcloud`,
   database `nextcloud_database`). **The dump is from Postgres 18 and will only load into an
   18-or-newer cluster** — check `docker exec nextcloud-aio-database postgres --version`
   before you start.

3. **Repair the skew.** This step is mandatory, not optional. `files:scan` rebuilds
   `oc_filecache` from what is actually on disk:

   ```sh
   docker exec -u www-data nextcloud-aio-nextcloud php occ maintenance:mode --on
   docker exec -u www-data nextcloud-aio-nextcloud php occ files:scan --all
   docker exec -u www-data nextcloud-aio-nextcloud php occ maintenance:mode --off
   ```

4. Run the [smoke test](nextcloud-smoke-test.md).

## After any use of the escape hatch

Expect user-visible oddities in the skew window: files that reappear, files that 404. Tell
whoever uses the instance. Trash and version history for affected files may also be
inconsistent.

---

## Restore rehearsal

**An untested restore is not a backup.** Rehearse this against a *scratch* instance — build
a volume from a snapshot, attach it to a throwaway box, confirm Nextcloud comes up and
serves files — rather than trusting the procedure on the day you need it.

| Date | Snapshot | Outcome | By |
| --- | --- | --- | --- |
| _(not yet rehearsed)_ | | | |

Record each rehearsal here.
