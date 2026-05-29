# Nextcloud instance — Ansible (over SSM)

Standalone Ansible that configures the Nextcloud instance in the `management`
environment. It reaches the host **only over AWS Systems Manager (SSM)** — there
is no SSH key and no inbound port 22. See
[ADR-0001](../../../docs/adr/0001-ansible-over-ssm.md) and [../CONTEXT.md](../CONTEXT.md).

```
ansible/
├── ansible.cfg                          # config (auto-loaded from this dir)
├── requirements.yml                     # pinned collections
├── inventory/
│   ├── management.aws_ec2.yml           # dynamic inventory (discovers by tag)
│   └── group_vars/nextcloud.yml         # aws_ssm connection wiring
└── playbooks/ping.yml                   # SSM connectivity tracer
```

`group_vars/` sits next to the inventory file so Ansible loads it for the
dynamically-discovered `nextcloud` group.

## Control-node prerequisites

The control node is the operator's workstation (not the instance). It needs:

- **AWS CLI v2** — <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>
- **Session Manager plugin** — the `aws_ssm` connection plugin shells out to it.
  <https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html>
  Verify with `session-manager-plugin --version`.
- **boto3 / botocore** — required by both the `aws_ec2` inventory plugin and the
  `aws_ssm` connection plugin. Install into the **same** Python environment that
  runs Ansible, e.g. `pip install boto3 botocore`.
- **Ansible collections** — install the pinned set:
  ```sh
  ansible-galaxy collection install -r requirements.yml
  ```
- **AWS credentials** with:
  - `ec2:DescribeInstances` (dynamic inventory discovery), and
  - `s3:PutObject` / `s3:GetObject` / `s3:DeleteObject` on the scratch bucket.

  The instance role needs **no** S3 permissions — only the control node's
  credentials touch the bucket (presigned URLs are generated here). See ADR-0001.

Provide credentials the usual way (`AWS_PROFILE`, env vars, or
`~/.aws/credentials`); the plugins read the ambient AWS configuration.

## Configure

The scratch bucket name is account-scoped and kept out of version control. Export
it from the Terraform output before running:

```sh
cd live/management/ansible
export SSM_SCRATCH_BUCKET="$(terraform -chdir=.. output -raw ssm_scratch_bucket_name)"
# Optional — defaults to eu-central-1:
export AWS_REGION="$(terraform -chdir=.. output -raw ssm_scratch_bucket_region)"
```

## Run the connectivity tracer

```sh
cd live/management/ansible

# Confirm the dynamic inventory discovers the instance by tag (no hardcoded ID/IP):
ansible-inventory --graph

# Prove the full SSM transport path end-to-end:
ansible-playbook playbooks/ping.yml
```

A successful `ansible.builtin.ping` (`pong`) confirms all three integration
layers: tag-based discovery, the SSM channel, and module-file transfer through
the scratch bucket.
