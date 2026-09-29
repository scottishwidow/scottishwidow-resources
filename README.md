## Prerequisites

### Tools

- Terraform 1.10 or later. The S3 backends use `use_lockfile`, which needs 1.10.

### AWS credentials

The Terraform roots keep their state in S3 buckets in `eu-central-1`:

| Roots | State bucket |
|---|---|
| `live/aws/management` | `tf-state-scottishwidow-management` |
| `live/hetzner/network`, `live/hetzner/openvpn` | `tf-state-scottishwidow-hetzner` |

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

The `live/hetzner/bootstrap` root creates the Hetzner state bucket and keeps its state locally. It needs only AWS credentials.
