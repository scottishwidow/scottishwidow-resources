# Context Map

## Contexts

- [Management](./live/management/CONTEXT.md) — the `management` AWS environment:
  the Nextcloud instance, its Terraform, and the Ansible that configures it.

## Relationships

- **Terraform → Ansible**: Terraform (`live/management/`) provisions the instance
  and supporting resources (EIP, Route 53 record, SSM scratch bucket); Ansible
  (`live/management/ansible/`) configures Nextcloud AIO on it, standalone (no
  `remote-exec`). They share no state file — Ansible discovers the instance via
  dynamic inventory (tags) and reads bucket/region from Terraform outputs.
