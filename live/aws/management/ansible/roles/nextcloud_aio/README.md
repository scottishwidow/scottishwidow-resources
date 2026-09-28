# `nextcloud_aio` role

Brings up the **Nextcloud AIO mastercontainer** in its default **built-in-Apache**
mode — base stack only (Apache + Nextcloud + PostgreSQL + Redis), no optional
containers. See [../../../CONTEXT.md](../../../CONTEXT.md) for the AIO / mastercontainer
language and [ADR-0001](../../../../docs/adr/0001-ansible-over-ssm.md) for the SSM transport.

## What it does

1. Asserts Docker Engine is present and reachable, failing clearly if not —
   Docker is installed by `user_data` at first boot (`live/management/user_data.sh`),
   not by this role.
2. Installs the Python Docker SDK (`python3-docker`) the `community.docker`
   modules need on the host.
3. Reconciles the `nextcloud/all-in-one` mastercontainer via
   `community.docker.docker_container` — idempotent on re-run.

The AIO admin interface (8080) is bound to **`127.0.0.1`**, so it is never
internet-exposed. The public data plane (80/443, TLS, domain) is a separate slice.

## Requires

- `become: true` (apt install + Docker socket access).
- The `community.docker` collection (pinned in `../../requirements.yml`).

## Variables

See [`defaults/main.yml`](defaults/main.yml). The volume name
`nextcloud_aio_mastercontainer` is hardcoded by AIO and must not be changed.

## Verify

After running `playbooks/nextcloud-aio.yml`, port-forward 8080 over SSM and open
the AIO setup page — see the project [README](../../README.md#verify-the-aio-mastercontainer).
