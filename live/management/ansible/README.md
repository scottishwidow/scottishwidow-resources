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
├── roles/
│   └── nextcloud_aio/                   # AIO mastercontainer (base stack)
└── playbooks/
    ├── ping.yml                         # SSM connectivity tracer
    └── nextcloud-aio.yml                # deploy the AIO mastercontainer
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

## Deploy the AIO mastercontainer

Brings up the Nextcloud AIO mastercontainer in its default built-in-Apache mode,
base stack only (Apache + Nextcloud + PostgreSQL + Redis). The AIO admin interface
on 8080 is bound to `127.0.0.1` — never internet-exposed. See the
[`nextcloud_aio` role](roles/nextcloud_aio/README.md).

```sh
cd live/management/ansible
ansible-playbook playbooks/nextcloud-aio.yml
```

Re-running is idempotent: the play reports `ok` (not `changed`) once the
mastercontainer is up.

### Verify the AIO mastercontainer

The admin interface is bound to localhost on the instance, so reach it with an
SSM **port-forward** — no public exposure, no SSH:

```sh
# Discover the instance by tag (same key the inventory uses):
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values=nextcloud Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].InstanceId' --output text)

# Forward local 8080 -> instance 8080 over SSM (leave this running):
aws ssm start-session \
  --target "$INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

Then open <https://localhost:8080> in a browser. AIO serves the admin interface
over HTTPS with a self-signed certificate, so accept the browser warning; the
**AIO setup page** (showing the initial admin password) confirms the
mastercontainer is up.
