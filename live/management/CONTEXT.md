# Management

The `management` AWS environment. It hosts a single self-managed **Nextcloud
instance** and contains both the Terraform that provisions it and the standalone
Ansible that configures it.

## Language

**Nextcloud instance**:
The single EC2 host (Graviton/arm64, `t4g.small`) that runs Nextcloud. Tagged
`Name=nextcloud`, reachable only via SSM.
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
