# 1. Configure the Nextcloud instance with Ansible over AWS SSM

Date: 2026-05-29

## Status

Accepted

## Context

The `nextcloud` EC2 instance in `live/management` is provisioned with a
deliberate invariant: **nothing reaches it except AWS Systems Manager (SSM)**.
There is no SSH key, no inbound port 22, and the instance IAM role is scoped to
exactly `AmazonSSMManagedInstanceCore` (see `live/management/main.tf`, commits
`8b6aa47` "remove key" and `f4c61ab` "enable SSM").

We want to configure Nextcloud AIO on this host with **standalone Ansible** (no
Terraform `remote-exec`; Ansible runs from a control node, not from Terraform).
Ansible's default transport is SSH, which this host intentionally does not
offer. So the transport is the decision everything else depends on.

## Decision

Connect with the **`amazon.aws.aws_ssm` connection plugin**, running every task
over the SSM channel.

Note the collection: the plugin used to live at `community.aws.aws_ssm`, which
is now a **deprecated redirect** to `amazon.aws.aws_ssm`. We use the canonical
`amazon.aws` path.

The plugin requires an **S3 bucket** as a file-transfer side-channel: the SSM
session carries commands, but module `.py` files (shipped on every task, even
`command`/`shell`) move through S3. We provision a dedicated **scratch bucket**
for this, with a lifecycle rule to expire objects, since the transferred files
are throwaway artifacts.

Crucially, the current plugin uses **presigned S3 URLs generated on the
controller**; the host fetches them with `curl`. Therefore:

- The **instance role needs no S3 permissions** — only network egress to S3,
  which it already has (`egress_rules = ["all-all"]`). The tight instance IAM
  posture is unchanged.
- Only the **control node's** AWS credentials need put/get/delete on the bucket.

Control-node prerequisites: AWS CLI v2, the Session Manager plugin, and
`boto3`/`botocore`.

## Consequences

- The "only SSM touches this box" invariant is preserved end-to-end. We add a
  capability rather than reopening a door.
- One new piece of infrastructure: an S3 scratch bucket (Terraform). No change
  to the instance IAM role.
- Tasks are slower than raw SSH (each module push is an S3 round-trip via a
  presigned URL). Irrelevant for a single host configured occasionally.
- There is **no S3-less mode** available today; it exists only as open feature
  requests (community.aws #2106, amazon.aws #2638). If a bucket-free transfer
  ships in a future pinned version, we can revisit and drop the bucket.

## Alternatives considered

- **SSM SSH proxy** (tunnel Ansible's ssh transport through
  `aws ssm start-session` / `AWS-StartSSHSession`). Rejected: still requires a
  public key on the host, which was deliberately removed — reintroduces key
  distribution on top of SSM complexity.
- **Re-add an SSH key and reopen port 22.** Rejected: simplest for Ansible but
  reverses a recent, explicit design decision. If ever chosen, it should be a
  conscious reversal of the SSM-only posture, not a convenience leak.
