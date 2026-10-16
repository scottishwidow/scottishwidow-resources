# Runbook: Split the management state

Move `module.vpc` and the Nextcloud modules out of `mgmt/terraform.tfstate` into their own
state keys. This runbook is the procedure for #119 (network checkpoint) and #120 (Nextcloud
checkpoint). The parent issue is #111.

This runbook **writes production state**. Read the whole procedure before you start.

## Transfer method

Use a controlled pull/move/push: pull the source state, move whole modules between local
copies with `terraform state mv`, verify the copies offline, then push.

Do not use `removed` and `import` blocks for the transfer. Import cannot restore the
Terraform-only attributes of four Nextcloud resources. A plan that imports them into the
Nextcloud root shows 4 in-place updates:

| Address | Attribute after import |
| --- | --- |
| `module.next_cloud.aws_iam_role.this[0]` | `force_detach_policies` |
| `module.next_cloud.aws_instance.ignore_ami[0]` | `user_data_replace_on_change`, `volume_tags`, `root_block_device[0].tags` |
| `module.next_cloud_sg.aws_security_group.this_name_prefix[0]` | `revoke_rules_on_delete`, `timeouts` |
| `module.ssm_scratch.aws_s3_bucket_public_access_block.this[0]` | `skip_destroy` |

A transfer plan must not contain updates. `state mv` keeps each object, its schema version,
and its private data unchanged.

The `removed { lifecycle { destroy = false } }` blocks in the old root stay. After the push
they match nothing. If the source push fails, they make sure that a plan forgets the module
and does not destroy it.

## Inventory

`mgmt/terraform.tfstate` holds 32 managed resource instances, all with provider
`provider["registry.terraform.io/hashicorp/aws"]`:

| Destination key | Modules | Instances |
| --- | --- | --- |
| `mgmt/network/terraform.tfstate` | `module.vpc` | 13 |
| `mgmt/nextcloud/terraform.tfstate` | `module.next_cloud`, `module.next_cloud_sg`, `module.next_cloud_backup`, `module.ssm_scratch` | 19 |

After both checkpoints, `mgmt/terraform.tfstate` holds no managed resources.

## Prerequisites

- Terraform `1.16.1`. AWS provider `6.47.0` from the committed lock files.
- The operator SSO role:

  ```sh
  export AWS_PROFILE=personal-management AWS_REGION=eu-central-1
  BUCKET=tf-state-scottishwidow-management
  REPO="$(git rev-parse --show-toplevel)"
  MGMT="$REPO/live/aws/management"
  ```

- A restricted work directory outside the repository, on a disk with space for the offline
  copies. State files contain secrets. A shared plugin cache keeps one copy of the provider.

  ```sh
  WORK="$(mktemp -d "$HOME/state-split.XXXXXX")"; chmod 700 "$WORK"; umask 077
  export TF_PLUGIN_CACHE_DIR="$WORK/plugin-cache"; mkdir "$TF_PLUGIN_CACHE_DIR"
  ```

- The private input `domain`. Supply it to the old root as you do today. Never commit it.
- A helper that lists managed instance addresses with their provider:

  ```sh
  addrs() {
    jq -r '.resources[] | select(.mode == "managed") as $r | $r.instances[]
      | "\($r.module // "").\($r.type).\($r.name)\(if has("index_key") then "[\(.index_key | tojson)]" else "" end) \($r.provider)"' "$1" | sort
  }
  ```

- A check that a saved plan changes no managed resource. It prints the offending addresses
  and fails if there are any:

  ```sh
  no_resource_changes() {
    local plan changed
    plan=$(terraform -chdir="$1" show -json "$2") || return 1
    changed=$(jq -r '.resource_changes[]?
      | select(.change.actions != ["no-op"]) | "\(.change.actions | join(",")) \(.address)"' <<<"$plan") || return 1
    [ -z "$changed" ] || { printf '%s\n' "$changed" >&2; return 1; }
  }
  ```

## Apply freeze

Hold the freeze from step 1 of checkpoint A to the end of checkpoint B.

- Run no `apply`, `import`, `state` command, or Ansible play against the management
  environment except the steps below.
- Merge nothing that touches `live/aws/management/` or `modules/`. Today this includes the
  Renovate PRs #144, #146, #147, and #175. They change files that the checkpoints move. Rebase
  them after the freeze.
- A per-key lock does not protect an operation over two keys. The freeze does.

## Stop conditions

Stop and go to [Recovery](#recovery) if one of these occurs:

- The source state version or serial differs from the value recorded at the pull.
- A destination key already exists.
- The state lists a workspace other than `default`, or the bucket has an `env:/` prefix.
- An address is missing, duplicated, or unknown, or has a different provider.
- A required input is missing.
- Any plan shows drift, or a managed-resource create, update, replace, destroy, or forget.
  Only the output changes listed in each step are permitted.
- A `state push` fails or asks for `-force`. Never use `-force`.

## Checkpoint A: network (#119)

Revision: the reviewed head of #195. Rehearsed at `628182f`. Record the commit you use.

```sh
REV_A=<head of #195>
```

### A1. Baseline

```sh
terraform version
aws s3api list-objects-v2 --bucket "$BUCKET" --query 'Contents[].Key'
aws s3api list-objects-v2 --bucket "$BUCKET" --prefix 'env:' --query 'Contents[].Key'
git -C "$REPO" switch main && git -C "$REPO" pull --ff-only
terraform -chdir="$MGMT" init -input=false
terraform -chdir="$MGMT" workspace show
terraform -chdir="$MGMT" plan -input=false -detailed-exitcode
```

Expected: the keys `mgmt/terraform.tfstate` and `mgmt/bootstrap/terraform.tfstate` only. No
`env:/` keys. Workspace `default`. The plan exits `0`.

### A2. Pull and back up

```sh
SRC_VERSION=$(aws s3api head-object --bucket "$BUCKET" --key mgmt/terraform.tfstate --query VersionId --output text)
terraform -chdir="$MGMT" state pull > "$WORK/source.tfstate"
cp "$WORK/source.tfstate" "$WORK/source.orig.tfstate"
jq '{serial, lineage}' "$WORK/source.orig.tfstate"
addrs "$WORK/source.orig.tfstate" | wc -l
```

Record `SRC_VERSION`, serial, and lineage. Expected: 32 addresses.

### A3. Move

Run in the work directory. It has no configuration, so `-state` and `-state-out` use local
files.

```sh
cd "$WORK"
terraform state mv -state=source.tfstate -state-out=network.tfstate 'module.vpc' 'module.vpc'
```

### A4. Verify the copies

```sh
addrs source.orig.tfstate > before.txt
{ addrs source.tfstate; addrs network.tfstate; } | sort > after.txt
diff before.txt after.txt && test -z "$(uniq -d after.txt)" && echo conserved
addrs network.tfstate | grep -vc '^module\.vpc\.'
addrs network.tfstate | wc -l
jq '{serial, lineage}' source.tfstate network.tfstate
```

Expected: `conserved`. `0` addresses outside `module.vpc`. 13 addresses in
`network.tfstate`. `source.tfstate` has the recorded lineage and a higher serial.
`network.tfstate` has a new lineage.

### A5. Plan offline

Plan both roots of `REV_A` against the local copies. The plans read AWS and write nothing.

```sh
mkdir "$WORK/rev-a" && git -C "$REPO" archive "$REV_A" | tar -x -C "$WORK/rev-a"
OFF="$WORK/rev-a/live/aws/management"
for root in "$OFF" "$OFF/network"; do
  printf 'terraform {\n  backend "local" {}\n}\n' > "$root/backend_override.tf"
done
cp source.tfstate "$OFF/terraform.tfstate"
cp network.tfstate "$OFF/network/terraform.tfstate"
for root in "$OFF" "$OFF/network"; do
  terraform -chdir="$root" init -input=false
  terraform -chdir="$root" plan -input=false -lock=false -out=offline.plan
  no_resource_changes "$root" offline.plan
done
```

Expected: the old root shows no changes. The network root shows no resource changes and
creates outputs `vpc_id` and `public_zone_1`.

A fresh `init` of the old root at `REV_A` selects `s3-bucket` 5.17.0. The deployed version is
5.16.1. The rehearsal showed no changes with 5.17.0. A change in `module.ssm_scratch` is a stop
condition.

### A6. Push the destination

```sh
git -C "$REPO" switch --detach "$REV_A"
NET="$MGMT/network"
aws s3api head-object --bucket "$BUCKET" --key mgmt/network/terraform.tfstate
terraform -chdir="$NET" init -input=false
terraform -chdir="$NET" state push "$WORK/network.tfstate"
terraform -chdir="$NET" plan -input=false -out="$WORK/network-outputs.plan"
no_resource_changes "$NET" "$WORK/network-outputs.plan"
terraform -chdir="$NET" apply "$WORK/network-outputs.plan"
terraform -chdir="$NET" output
```

Expected: `head-object` returns `404`. The plan only creates the two outputs. The outputs are
the VPC and the subnet of the running Nextcloud instance.

### A7. Push the source

```sh
test "$(aws s3api head-object --bucket "$BUCKET" --key mgmt/terraform.tfstate --query VersionId --output text)" = "$SRC_VERSION"
terraform -chdir="$MGMT" init -input=false
terraform -chdir="$MGMT" state push "$WORK/source.tfstate"
terraform -chdir="$MGMT" plan -input=false -detailed-exitcode
terraform -chdir="$NET" plan -input=false -detailed-exitcode
```

Expected: the version matches. Both plans exit `0`.

### A8. Integrate

Mark #195 ready and merge it. Then on `main`, run `plan -detailed-exitcode` for the old root
and the network root again. Both exit `0`. Record the evidence in #119. Delete `$WORK/rev-a`.
Keep `$WORK` until checkpoint B ends.

## Checkpoint B: Nextcloud (#120)

Revision: the reviewed head of #196, rebased on `main` after A8. Rehearsed at `03f32b2`.

```sh
REV_B=<head of #196>
NC="$MGMT/nextcloud"
```

### B1. Baseline

Repeat A1 on `main`. Also run `terraform -chdir="$NET" plan -detailed-exitcode`. Expected
keys: `mgmt/terraform.tfstate`, `mgmt/bootstrap/terraform.tfstate`, and
`mgmt/network/terraform.tfstate`. Both plans exit `0`.

### B2. Pull and back up

```sh
SRC_VERSION=$(aws s3api head-object --bucket "$BUCKET" --key mgmt/terraform.tfstate --query VersionId --output text)
terraform -chdir="$MGMT" state pull > "$WORK/source-b.tfstate"
cp "$WORK/source-b.tfstate" "$WORK/source-b.orig.tfstate"
jq '{serial, lineage}' "$WORK/source-b.orig.tfstate"
addrs "$WORK/source-b.orig.tfstate" | wc -l
```

Expected: 19 addresses, none in `module.vpc`.

### B3. Move

```sh
cd "$WORK"
for m in module.next_cloud module.next_cloud_sg module.next_cloud_backup module.ssm_scratch; do
  terraform state mv -state=source-b.tfstate -state-out=nextcloud.tfstate "$m" "$m"
done
```

### B4. Verify the copies

```sh
addrs source-b.orig.tfstate > before-b.txt
{ addrs source-b.tfstate; addrs nextcloud.tfstate; } | sort > after-b.txt
diff before-b.txt after-b.txt && test -z "$(uniq -d after-b.txt)" && echo conserved
addrs source-b.tfstate | wc -l
addrs nextcloud.tfstate | wc -l
jq '{serial, lineage}' source-b.tfstate nextcloud.tfstate
```

Expected: `conserved`. 0 addresses in `source-b.tfstate`. 19 addresses in `nextcloud.tfstate`.

### B5. Place the private input

Put `domain` in `$NC/secret.auto.tfvars`. Remove it from the old root's input location. Git
ignores `*.tfvars`. Check that `git -C "$REPO" status --short` does not list the file.

### B6. Plan offline

Do A5 with `REV_B`, the roots `"$OFF"` and `"$OFF/nextcloud"`, and the copies
`source-b.tfstate` and `nextcloud.tfstate`. Copy `secret.auto.tfvars` into
`"$OFF/nextcloud"`.

Expected: the old root shows no resource changes and deletes its five outputs. The Nextcloud
root shows no resource changes and creates outputs `next_cloud_public_ip`,
`next_cloud_domain`, `next_cloud_backup_policy_id`, `ssm_scratch_bucket_name`, and
`ssm_scratch_bucket_region`. Compare their values with `terraform -chdir="$MGMT" output`.

### B7. Push the destination

Do A6 with `REV_B`, `"$NC"`, key `mgmt/nextcloud/terraform.tfstate`, and
`"$WORK/nextcloud.tfstate"`. Expected: the plan only creates the five outputs.

### B8. Push the source

Do A7 with `"$WORK/source-b.tfstate"`. For the old root, the plan deletes its five outputs and
changes nothing else. Apply that saved plan after `no_resource_changes` passes. Then the old
root, the network root, and the Nextcloud root each plan with exit `0`.

### B9. Check the operator paths

```sh
cd "$NC/ansible"
terraform -chdir=.. output
export SSM_SCRATCH_BUCKET="$(terraform -chdir=.. output -raw ssm_scratch_bucket_name)"
export AWS_REGION="$(terraform -chdir=.. output -raw ssm_scratch_bucket_region)"
ansible-inventory --graph
ansible-playbook playbooks/ping.yml
```

Expected: the inventory has one `nextcloud` host. The ping succeeds over SSM.

### B10. Integrate and end the freeze

Mark #196 ready and merge it. On `main`, plan all three roots and bootstrap. All exit `0`.
Record the evidence in #120. Delete `$WORK`. End the freeze. #122 retires the old root.

## Recovery

State objects have Object Lock GOVERNANCE retention for 5 days. Do not delete object versions.
A plain delete adds a delete marker; #113 verified that Object Lock allows this. Restore a
version by copying it.

```sh
restore_source() {
  aws s3api copy-object --bucket "$BUCKET" --key mgmt/terraform.tfstate \
    --copy-source "$BUCKET/mgmt/terraform.tfstate?versionId=$SRC_VERSION"
}
drop_destination() {
  aws s3api delete-object --bucket "$BUCKET" --key "$1"
}
```

| Failure | State of the keys | Action |
| --- | --- | --- |
| Before the destination push (A2 to A5, B2 to B6) | Unchanged | Delete the local copies. Find the cause. Start again at step 1. |
| Destination push fails | Source unchanged. Destination absent or partial. | `drop_destination <key>`. Start again at step 1. |
| Destination output apply fails | Both keys own the modules | `drop_destination <key>`. Start again at step 1. |
| Source push fails | Both keys own the modules | Keep the freeze. Check that the remote version is still `SRC_VERSION` and retry the push. If it does not succeed, `drop_destination <key>`. |
| A plan after the source push is not clean | Moved | `restore_source`, then `drop_destination <key>`. Plan the old root on `main`. It must exit `0`. |
| A problem found after integration | Moved, config merged | Revert the merge commit. Then `restore_source` with the version from step 2 and `drop_destination <key>`. |

The rollback configuration is `main` before the checkpoint merge. Never run `apply` on a
root whose plan is not clean. After a rollback, `terraform state pull` from the old root must
list the same addresses as `$WORK/source.orig.tfstate` (or `source-b.orig.tfstate`).
