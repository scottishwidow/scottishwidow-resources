# scottishwidow-infrastructure

## Environments

| Environment | Path | Documentation |
|---|---|---|
| Management | `live/aws/management` | [CONTEXT.md](./live/aws/management/CONTEXT.md) |
| OVPN | `live/hetzner/ovpn` | [OVPN provisioning](#ovpn-provisioning) |
| Honeynet | `live/hetzner/honeynet` | [Honeynet](./live/hetzner/honeynet/README.md) |

## Prerequisites

### Tools

- Terraform 1.10 or later. The S3 backends use `use_lockfile`, which needs 1.10.
- GNU Make, to provision the Hetzner roots in the correct order.
- Ansible, to configure the hosts.

### AWS credentials

The Terraform roots keep their state in S3 buckets in `eu-central-1`:

| Roots | State bucket |
|---|---|
| `live/aws/management` | `tf-state-scottishwidow-management`, key `mgmt/terraform.tfstate` |
| `live/aws/management/bootstrap` | `tf-state-scottishwidow-management`, key `mgmt/bootstrap/terraform.tfstate` |
| `live/hetzner/ovpn/*` | `tf-state-scottishwidow-hetzner`, keys under `ovpn/` |
| `live/hetzner/honeynet/*` | `tf-state-scottishwidow-hetzner`, keys under `honeynet/` |

The credentials must be able to read, write and delete objects in the bucket, including the `.tflock` lock file.

```sh
export AWS_PROFILE=<profile>
```

### Hetzner Cloud tokens

Each Hetzner environment has its own Hetzner Cloud project and API token with Read & Write permission:

```sh
export OVPN_HCLOUD_TOKEN=<token>
export HONEYNET_HCLOUD_TOKEN=<token>
```

Each Makefile gives its token to Terraform as `HCLOUD_TOKEN`. It ignores an `HCLOUD_TOKEN` that the shell already exports.

### Management bootstrap

`live/aws/management/bootstrap` owns the management state bucket. Its state is in that bucket, at `mgmt/bootstrap/terraform.tfstate`.

For a new environment, the bucket does not exist yet. Do these steps in this sequence:

1. Create `backend_override.tf` in the bootstrap root. Git ignores this file.

   ```hcl
   terraform {
     backend "local" {}
   }
   ```

2. Create the bucket with local state:

   ```sh
   terraform init
   terraform apply
   ```

3. Delete `backend_override.tf`. Then move the local state to the bucket:

   ```sh
   terraform init -migrate-state
   ```

Do not do these steps for an environment that already has its bucket.

### Hetzner bootstrap

`live/hetzner/ovpn/bootstrap` creates the Hetzner state bucket, which both environments share, and the OVPN admin SSH key. It keeps its state locally. Apply it manually before all other Hetzner roots:

```sh
cd live/hetzner/ovpn/bootstrap
HCLOUD_TOKEN=$OVPN_HCLOUD_TOKEN terraform apply
```

## OVPN provisioning

Use the Makefile in `live/hetzner/ovpn`. It stops if `AWS_PROFILE` or `OVPN_HCLOUD_TOKEN` is not set.

| Command | Order |
|---|---|
| `make init`, `make apply` | `network`, `openvpn`, `private_hosts` |
| `make destroy` | `private_hosts`, `openvpn`, `network` |

To run one action on one root, use `make <action>-<root>`. To pass arguments to Terraform, use `TF_ARGS`:

```sh
make plan-network TF_ARGS=-refresh=false
```

Obey these rules:

- Apply `openvpn` before `private_hosts`. The Gateway uses the fixed private IP `10.10.0.2`. If a Private Host is created first, Hetzner can give that IP to the Private Host.
- There is no `make plan` for all roots. `openvpn` and `private_hosts` read the network with data sources, so their plan does not show changes that are not yet applied to `network`. Plan and apply one root at a time.
- The Makefile does not manage `bootstrap`, because it holds the state bucket of the other roots.
- `make destroy` stops at `openvpn` because the Gateway primary IPv4 has delete protection. Remove the protection manually if you must delete the IP.

## Honeynet provisioning

See [live/hetzner/honeynet/README.md](./live/hetzner/honeynet/README.md#provisioning).
