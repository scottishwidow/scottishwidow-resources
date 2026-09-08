# Context Map

## Contexts

- [Management](./live/management/CONTEXT.md) — the `management` AWS environment:
  the Nextcloud and Song Vault instances, their Terraform, and the Ansible that
  configures Nextcloud.
- **IaC security triage — archived.** The pipeline that scanned the Terraform for
  misconfigurations, assigned each finding a verdict with a rationale, and proposed
  a patch where a human asked for one. It was a proof of concept, it worked, and its
  code, workflows and design are held at the tag `poc/iac-security-triage` rather
  than on `main`. Trivy still scans and still raises alerts; nothing triages them.
  To bring it back, see [the restore runbook](./docs/runbooks/iac-security-triage-restore.md).

## Relationships

- **Terraform → Ansible**: Terraform (`live/management/`) provisions the instance
  and supporting resources (EIP, Route 53 record, SSM scratch bucket); Ansible
  (`live/management/ansible/`) configures Nextcloud AIO on it, standalone (no
  `remote-exec`). They share no state file — Ansible discovers the instance via
  dynamic inventory (tags) and reads bucket/region from Terraform outputs.
- **DNS**: the Route 53 hosted zone is to be imported into and owned by
  `live/management/` (issue #20). Once the import lands, the manual `UPSERT`
  procedure documented in `live/management/CONTEXT.md` is no longer accurate.
- **Scan → Management (reads only)**: Trivy reads every `.tf` file in the repo,
  but it provisions nothing and holds no AWS credentials — it reads *code*, never
  live infrastructure. Its findings reach code scanning as alerts and stop there
  while triage is archived.
- **ADRs, design docs → nothing**: they are *not* agent input, and the machinery
  that made them so is deleted. `docs/design/` is where development thinking is
  worked out and is half-formed by design; feeding it to an agent promoted drafts
  to facts. A new ADR changes what an agent sees only by changing the Terraform.
  This is the line ADR-0008 draws, and the corpus assembler is the one place it
  could be quietly crossed — it may contain code and never prose.
