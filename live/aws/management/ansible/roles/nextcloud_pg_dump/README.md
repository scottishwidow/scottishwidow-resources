# `nextcloud_pg_dump` role

Installs a **systemd timer** that writes a gzipped `pg_dumpall` of the Nextcloud AIO
Postgres cluster to `/var/backups/nextcloud/` on the **root disk** — deliberately, so the
dump is captured inside the same nightly EBS snapshot as everything else.

Runs **after** `nextcloud_aio` (the database container must exist first).

## This is an escape hatch, not a restore path

The real backup is the EBS snapshot (see [ADR-0003](../../../../docs/adr/0003-ebs-snapshot-backups-via-dlm.md)).
Because the whole instance lives on one volume, a snapshot captures Postgres **and** the
file blobs at the same instant — coherently.

This dump does **not** have that property. Nextcloud keeps file blobs on the filesystem and
their metadata in Postgres, so pairing a 04:00 dump with a 04:30 filesystem reintroduces
exactly the skew the snapshot eliminates: files uploaded in that window exist on disk but
are invisible to Nextcloud, and files deleted in it are referenced by the database but gone.

Reach for it **only** when the Postgres cluster itself is corrupt and will not WAL-replay,
and expect to repair with `occ files:scan --all` afterwards. See
[the restore runbook](../../../../docs/runbooks/nextcloud-restore.md).

## What it does

1. Creates `{{ nextcloud_pg_dump_dir }}` (default `/var/backups/nextcloud`), `0700` root-only.
2. Installs `/usr/local/bin/nextcloud-pg-dump.sh`, which dumps via
   `docker exec {{ nextcloud_pg_dump_container }} sh -c 'pg_dumpall -U "$POSTGRES_USER"'`.
   The username is read from the **container's own environment** rather than hardcoded —
   AIO has changed it before. (It is currently `nextcloud`, on Postgres 18.)
3. Installs and enables `nextcloud-pg-dump.timer`, firing at
   `{{ nextcloud_pg_dump_oncalendar }}` (default `04:00` UTC, 30 min before the DLM
   snapshot) with `Persistent=true` so a run missed while the instance was down fires on
   next boot.
4. Keeps the newest `{{ nextcloud_pg_dump_keep }}` dumps (default `3`) and prunes the rest.

The script writes to a `.partial` file and renames only after verifying the dump ends with
Postgres' `dump complete` trailer, so a half-written dump is never published as a good one.
`set -o pipefail` is load-bearing here: without it a failing `pg_dumpall` would still exit 0
through `gzip`.

## Requires

- `become: true` (writes to `/var/backups`, `/usr/local/bin`, `/etc/systemd/system`).
- Docker running, with the AIO database container up.

## Variables

See [`defaults/main.yml`](defaults/main.yml).

## Verify

```sh
systemctl list-timers nextcloud-pg-dump      # timer is scheduled
systemctl start nextcloud-pg-dump.service    # force a run
journalctl -u nextcloud-pg-dump -n 20        # should report the written path + size
ls -lh /var/backups/nextcloud/               # non-empty pg-YYYY-MM-DD.sql.gz
gzip -t /var/backups/nextcloud/pg-*.sql.gz   # gzip integrity
```
