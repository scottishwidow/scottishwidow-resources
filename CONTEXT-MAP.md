# Context Map

## Contexts

- [Management](./live/aws/management/CONTEXT.md) — the `management` AWS environment:
  the Nextcloud instance, its Terraform, and the Ansible that configures it.
- [OVPN](./live/hetzner/ovpn/CONTEXT.md) — the `ovpn` Hetzner Cloud environment:
  the Gateway and the Private Hosts behind it.
- [Honeynet](./live/hetzner/honeynet/CONTEXT.md) — the `honeynet` environment: Honeypots
  that attract attacks for Suricata to inspect.
- **IaC security triage — archived.** The pipeline that scanned the Terraform for
  misconfigurations, assigned each finding a verdict with a rationale, and proposed
  a patch where a human asked for one. It was a proof of concept, it worked, and its
  code, workflows and design are held at the tag `poc/iac-security-triage` rather
  than on `main`. Trivy still scans and still raises alerts; nothing triages them.
  To bring it back, see [the restore runbook](./docs/runbooks/iac-security-triage-restore.md).

## Relationships

- **Honeynet → nothing**: the Honeynet shares no network, Hetzner project, Hetzner
  token or SSH key with any other context. Nothing in another context may route to
  it or trust it.
- **Honeynet → OVPN (state only)**: the Honeynet keeps its state files under
  their own keys in the Hetzner state bucket, which the OVPN bootstrap creates.
  The OVPN bootstrap must exist first. This is the only shared resource.

- **Terraform → Ansible**: Terraform (`live/aws/management/nextcloud/`) provisions
  the instance and supporting resources (EIP, backup policy, SSM scratch bucket);
  Ansible (`live/aws/management/nextcloud/ansible/`) configures Nextcloud AIO on it,
  standalone (no `remote-exec`). They share no state file — Ansible discovers the
  instance via dynamic inventory (tags) and reads bucket/region from Terraform outputs.
- **DNS**: Route 53 is outside Terraform. The operator updates the A record manually
  with the `UPSERT` procedure in `live/aws/management/CONTEXT.md`.
- **Scan → Management (reads only)**: Trivy reads every `.tf` file in the repo,
  but it provisions nothing and holds no AWS credentials — it reads *code*, never
  live infrastructure. Its findings reach code scanning as alerts and stop there
  while triage is archived.
- **ADRs, design docs → nothing**: they are *not* agent input. This is the line
  ADR-0008 draws. `main` has no agent and no `docs/design/` while triage is
  archived. If triage is restored, its corpus assembler is the one place the line
  could be quietly crossed — it may contain code and never prose.
