# Management

The `management` AWS environment. It hosts two self-managed EC2 instances — the
**Nextcloud instance** and the **Song Vault instance** — and contains the
Terraform that provisions them and the standalone Ansible that configures
Nextcloud.

## Language

**Nextcloud instance**:
The single EC2 host (Graviton/arm64, `t4g.small`) that runs Nextcloud. Tagged
`Name=nextcloud`, reachable only via SSM.
_Avoid_: server, box, VM (in docs/code).

**Song Vault instance**:
A second EC2 host (Graviton/arm64, `t4g.small`) tagged `Name=song-vault`,
reachable only via SSM. Its data plane opens 80/443 to the world via its own
security group, but — unlike the Nextcloud instance — it has no Elastic IP and no
`domain`, so it carries only an auto-assigned (non-durable) public IP. Currently a
Terraform skeleton with no Ansible configuration yet.
_Avoid_: server, box, VM (in docs/code).

**Nextcloud AIO**:
Nextcloud's All-in-One distribution. Not one container — a stack (Apache,
Nextcloud/PHP-FPM, PostgreSQL, Redis) orchestrated by a single **mastercontainer**.
_Avoid_: "Nextcloud" alone when you mean the whole AIO stack.

**Mastercontainer**:
The `nextcloud/all-in-one` container that manages the rest of the AIO stack via
the Docker socket and serves the AIO admin interface on port 8080.

**Control node**:
The machine that runs Ansible — here, the operator's local workstation. Not the
Nextcloud instance.
_Avoid_: controller, runner.

**Scratch bucket**:
The S3 bucket the `amazon.aws.aws_ssm` connection plugin uses as a file-transfer
side-channel (module `.py` files move through it via presigned URLs). Transient
contents; lifecycle-expired.
_Avoid_: state bucket (that is the separate Terraform backend bucket).

**SSM connection**:
The `amazon.aws.aws_ssm` Ansible connection plugin. The only transport to the
instance — no SSH, no inbound 22. See ADR-0001.

**Public address**:
An Elastic IP (the ec2-instance module's `create_eip`) gives the instance a stable
address that survives the instance replacement triggered by `user_data` edits. The data plane
is world-facing: the security group opens 80/443 to `0.0.0.0/0` so AIO can serve
clients and complete Let's Encrypt HTTP-01 validation. The control plane stays
SSM-only.
_Avoid_: confusing this with the auto-assigned public IP (not durable).

## Out-of-band: Route 53 A record

Route 53 is **not** managed by Terraform here (importing the existing zone is out
of scope — see issue #20). After `terraform apply`, point the `domain` at the EIP
manually. This is a HITL follow-up step, run once the EIP exists:

```sh
cd live/management
DOMAIN=$(terraform output -raw next_cloud_domain)
EIP=$(terraform output -raw next_cloud_public_ip)
aws route53 change-resource-record-sets \
  --hosted-zone-id Z01225632CGMCYQJ151NK \
  --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"${DOMAIN}\",\"Type\":\"A\",\"TTL\":300,\"ResourceRecords\":[{\"Value\":\"${EIP}\"}]}}]}"
```

`UPSERT` is idempotent — safe to re-run if the EIP ever changes. Verify with
`dig +short ${DOMAIN}` once propagated.
