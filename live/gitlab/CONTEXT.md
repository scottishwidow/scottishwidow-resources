# GitLab

The `gitlab` environment: a self-hosted GitLab deployment on AWS, modelled on
GitLab's 2k reference architecture with managed AWS services in place of the
self-managed Postgres and Redis nodes. Nothing is provisioned yet — see
[the design draft](../../docs/design/gitlab-on-aws.md) and
[ADR-0004](../../docs/adr/0004-gitlab-downsized-2k-reference-architecture.md),
[ADR-0005](../../docs/adr/0005-gitlab-backup-strategy.md),
[ADR-0006](../../docs/adr/0006-gitlab-secrets-architecture.md).

## Language

**Node role**:
What a given EC2 host runs — `rails`, `sidekiq`, or `gitaly`. Every host runs the
same `gitlab-ee` Linux package; the role is expressed purely in `gitlab.rb`, by
which services are enabled. Roles are how instances are tagged, how the Ansible
dynamic inventory groups them, and how the Terraform node primitive is
parameterised.
_Avoid_: "server type", "tier".

**Rails node**:
A host serving the web/API workload (Puma) and Git-over-SSH (gitlab-shell). There
are two, behind the load balancer. Being able to run two is the point — it is what
forces shared state to be genuinely externalised.
_Avoid_: "web node" when gitlab-shell matters, "frontend".

**Sidekiq node**:
The host running background job processing. One, not load-balanced.

**Gitaly node**:
The single host that serves Git repository storage. Stateful in a way no other node
is: it owns the repository volume. Not a Gitaly Cluster — there is no Praefect here.
_Avoid_: "git server", "storage node" (ambiguous with object storage).

**Repository volume**:
The separate encrypted EBS volume attached to the Gitaly node holding all Git
repositories. Deliberately *not* the root disk, so the node can be replaced without
touching repository data. Cannot be object storage or a network filesystem —
GitLab requires local block storage for repositories.
_Avoid_: "data disk" alone; "the Gitaly disk" when you mean the root volume.

**Object storage**:
The set of S3 buckets holding everything GitLab is willing to keep off local disk —
artifacts, LFS, uploads, MR diffs, packages, dependency proxy, Terraform state,
registry images, Pages, secure files, and native backups. One bucket per data type,
addressed through GitLab's *consolidated* configuration and reached by instance
profile, never static keys.
_Avoid_: "the bucket" (singular); confusing the `terraform-state` bucket here — which
holds GitLab's *own* Terraform-state feature data — with this repo's Terraform backend
bucket.

**Master credentials**:
The RDS-generated database superuser credentials, owned and rotated by RDS in Secrets
Manager. Used only to administer the database. GitLab never connects with these.
_Avoid_: "the DB password".

**App role**:
The separate PostgreSQL role GitLab actually connects as, granted `rds_superuser`,
with its own non-rotating secret. Created from inside the VPC, not by Terraform.
_Avoid_: "the gitlab user" (ambiguous with the OS user, the Git user, and the GitLab
application's root account).

**Secrets file**:
`/etc/gitlab/gitlab-secrets.json` — the keys that encrypt stored CI variables, 2FA
secrets and tokens. Generated once, then preserved outside the node and reinstated on
every rebuild. Deliberately excluded from GitLab's own backup, because storing it
beside the data it decrypts would defeat the encryption. Losing it is unrecoverable in
a way that losing a node is not.
_Avoid_: "the secrets" (ambiguous with Secrets Manager and Parameter Store contents).

**Restore path**:
GitLab's native backup — the only artefact that can reconstitute database, repositories
and blobs as one coherent whole. Distinct from the **floor**: RDS automated backups,
scheduled snapshots of the repository volume, and bucket versioning, which each protect
one store independently and cannot be combined into a consistent point in time.
_Avoid_: "backup" unqualified — here it always means one or the other, never both.

**Required stop**:
A GitLab version that must be upgraded *to* before any later version can be installed.
Since 17.5 they fall at `x.2`, `x.5`, `x.8` and `x.11`. Because the database and
repository volume outlive every node, the installed package version is pinned exactly —
an unpinned rebuild could arrive at a version that cannot read the data it mounts.

## Relationship to `management`

The Route 53 hosted zone is owned by [`live/management`](../management/CONTEXT.md).
This environment resolves it by name and manages only its own records.

The atomic-snapshot property that makes the Nextcloud backup restorable (see ADR-0003)
**does not hold here**. State is split across three stores that cannot be captured at a
single instant, which is why the restore path and the floor are separate concepts above.
