# `system_swap` role

Provisions a persistent **swap file** on the instance. The Nextcloud box is a
`t4g.small` (2 GB RAM) with no swap by default; under load the full AIO stack can
exhaust memory and trip the kernel **OOM killer** (observed killing Collabora
workers, leaving the stack degraded). A small swap file gives the kernel an
overflow buffer instead of killing processes outright.

Runs **before** `nextcloud_aio` so swap exists before the stack starts.

## What it does

1. Allocates `{{ system_swap_file }}` (default `/swapfile`, `2048` MB) if missing,
   `0600` root-only.
2. Formats it with `mkswap` (skipped if it already carries a swap signature).
3. Persists it in `/etc/fstab` and enables it with `swapon` — idempotent on re-run.
4. Sets `vm.swappiness={{ system_swap_swappiness }}` (default `10`) via
   `/etc/sysctl.d/99-swappiness.conf` so swap is overflow, not first resort.

## Requires

- `become: true` (writes to `/`, `/etc/fstab`, `/etc/sysctl.d`, calls `swapon`).

## Variables

See [`defaults/main.yml`](defaults/main.yml).

## Verify

`swapon --show` should list `/swapfile`; `free -m` should report a non-zero
`Swap` total.
