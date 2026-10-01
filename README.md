## Prerequisites

### Tools

- Terraform 1.10 or later. The S3 backends use `use_lockfile`, which needs 1.10.
- GNU Make, to provision the Hetzner roots in the correct order.

### AWS credentials

The Terraform roots keep their state in S3 buckets in `eu-central-1`:

| Roots | State bucket |
|---|---|
| `live/aws/management` | `tf-state-scottishwidow-management` |
| `live/hetzner/network`, `live/hetzner/openvpn`, `live/hetzner/private_hosts` | `tf-state-scottishwidow-hetzner` |

The credentials must be able to read, write and delete objects in the bucket, including the `.tflock` lock file.

Set the AWS profile before you run Terraform:

```sh
export AWS_PROFILE=<profile>
```

### Hetzner Cloud token

The Hetzner roots also need a Hetzner Cloud API token with Read & Write permission:

```sh
export HCLOUD_TOKEN=<token>
```

The `live/hetzner/bootstrap` root creates the Hetzner state bucket and the admin SSH key. It keeps its state locally. Apply it manually before the other Hetzner roots.

## Hetzner provisioning

The Hetzner roots depend on each other. Apply `live/hetzner/bootstrap` first. Then use the Makefile in `live/hetzner` to apply them in the correct order. It stops if `AWS_PROFILE` or `HCLOUD_TOKEN` is not set.

| Command | Order |
|---|---|
| `make init`, `make plan`, `make apply` | `network`, `openvpn`, `private_hosts` |
| `make destroy` | `private_hosts`, `openvpn`, `network` |

To run one action on one root, use `make <action>-<root>`:

```sh
cd live/hetzner
make apply-openvpn
```

To pass arguments to Terraform, use `TF_ARGS`:

```sh
make plan TF_ARGS=-refresh=false
```

Obey these rules:

- Apply `openvpn` before `private_hosts`. The Gateway uses the fixed private IP `10.10.0.2`. If a Private Host is created first, Hetzner can give that IP to the Private Host.
- On a new environment, `make plan` fails for `openvpn` and `private_hosts` because the network does not exist yet. Use `make apply`.
- The Makefile does not manage `bootstrap`, because it holds the state bucket of the other roots.
- `make destroy` stops at `openvpn` because the Gateway primary IPv4 has delete protection. Remove the protection manually if you must delete the IP.
