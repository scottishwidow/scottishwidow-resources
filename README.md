## Prerequisites

### Tools

- Terraform 1.10 or later. The S3 backends use `use_lockfile`, which needs 1.10.
- GNU Make, to provision the Hetzner roots in the correct order.

### AWS credentials

The Terraform roots keep their state in S3 buckets in `eu-central-1`:

| Roots | State bucket |
|---|---|
| `live/aws/management` | `tf-state-scottishwidow-management` |
| `live/hetzner/ovpn/{network,openvpn,private_hosts}` | `tf-state-scottishwidow-hetzner`, keys under `ovpn/` |
| `live/hetzner/honeynet/{network,sensor}` | `tf-state-scottishwidow-hetzner`, keys under `honeynet/` |

The credentials must be able to read, write and delete objects in the bucket, including the `.tflock` lock file.

Set the AWS profile before you run Terraform:

```sh
export AWS_PROFILE=<profile>
```

### Hetzner Cloud tokens

Each Hetzner project has its own Hetzner Cloud project and API token. The tokens need Read & Write permission:

| Project | Token |
|---|---|
| `live/hetzner/ovpn` | `OVPN_HCLOUD_TOKEN` |
| `live/hetzner/honeynet` | `HONEYNET_HCLOUD_TOKEN` |

```sh
export OVPN_HCLOUD_TOKEN=<token>
export HONEYNET_HCLOUD_TOKEN=<token>
```

Each Makefile gives its token to Terraform as `HCLOUD_TOKEN`. It ignores an `HCLOUD_TOKEN` that the shell already exports.

The `live/hetzner/ovpn/bootstrap` root creates the Hetzner state bucket, which both projects share, and the OVPN admin SSH key. It keeps its state locally. Apply it manually before all other Hetzner roots, including the Honeynet roots:

```sh
cd live/hetzner/ovpn/bootstrap
HCLOUD_TOKEN=$OVPN_HCLOUD_TOKEN terraform apply
```

## OVPN provisioning

The OVPN roots depend on each other. Apply `live/hetzner/ovpn/bootstrap` first. Then use the Makefile in `live/hetzner/ovpn` to apply them in the correct order. It stops if `AWS_PROFILE` or `OVPN_HCLOUD_TOKEN` is not set.

| Command | Order |
|---|---|
| `make init`, `make apply` | `network`, `openvpn`, `private_hosts` |
| `make destroy` | `private_hosts`, `openvpn`, `network` |

To run one action on one root, use `make <action>-<root>`:

```sh
cd live/hetzner/ovpn
make apply-openvpn
```

To pass arguments to Terraform, use `TF_ARGS`:

```sh
make plan-network TF_ARGS=-refresh=false
```

Obey these rules:

- Apply `openvpn` before `private_hosts`. The Gateway uses the fixed private IP `10.10.0.2`. If a Private Host is created first, Hetzner can give that IP to the Private Host.
- There is no `make plan` for all roots. The `openvpn` and `private_hosts` roots read the network with data sources, so their plan does not show changes that are not yet applied to `network`. Use `make plan-<root>` on one root at a time, and apply it before you plan the next root.
- The Makefile does not manage `bootstrap`, because it holds the state bucket of the other roots.
- `make destroy` stops at `openvpn` because the Gateway primary IPv4 has delete protection. Remove the protection manually if you must delete the IP.

## Honeynet provisioning

Apply `live/hetzner/ovpn/bootstrap` first, because the Honeynet roots keep their state in its bucket. Then use the Makefile in `live/hetzner/honeynet`. It stops if `AWS_PROFILE` or `HONEYNET_HCLOUD_TOKEN` is not set.

| Command | Order |
|---|---|
| `make init`, `make apply` | `bootstrap`, `network`, `sensor` |
| `make destroy` | `sensor`, `network`, `bootstrap` |

The Honeynet `bootstrap` root creates only the Honeynet SSH key. It keeps its state locally, so the Makefile manages it with the other roots.

To configure and check the Sensor after `make apply`:

```sh
cd live/hetzner/honeynet
make configure
make verify
```
