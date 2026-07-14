#########################
# Nextcloud backups (DLM)
#########################

# All Nextcloud state — Postgres metadata and the file blobs alike — lives in Docker
# volumes on the instance's single root volume. One EBS snapshot therefore captures the
# database and the files at the same instant, which is what makes a restore coherent.
# Snapshots are crash-consistent, not application-quiesced: Postgres WAL-replays on
# restore exactly as it would after a power cut. See docs/adr/0003.

data "aws_iam_policy_document" "dlm_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "next_cloud_dlm" {
  name               = "${var.next_cloud_instance_name}-dlm-lifecycle"
  description        = "Assumed by Data Lifecycle Manager to snapshot the ${var.next_cloud_instance_name} instance."
  assume_role_policy = data.aws_iam_policy_document.dlm_assume_role.json

  tags = var.tags
}

# No SSM permissions are attached: the policy runs no pre/post scripts. AWS ships no
# Linux app-consistent snapshot document (only Windows VSS and SAP HANA), and freezing
# the root filesystem risks deadlocking the agent meant to thaw it.
resource "aws_iam_role_policy_attachment" "next_cloud_dlm" {
  role       = aws_iam_role.next_cloud_dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "next_cloud" {
  # DLM restricts the description charset to [0-9A-Za-z _-]; colons and slashes are rejected.
  description        = "Nextcloud EBS snapshots - ${var.next_cloud_backup_daily_count} daily ${var.next_cloud_backup_weekly_count} weekly ${var.next_cloud_backup_monthly_count} monthly"
  execution_role_arn = aws_iam_role.next_cloud_dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["INSTANCE"]

    # Verified against the live instance: the ec2-instance module's `name` argument wins
    # over the `Name` key in `tags`, so the instance is tagged Name=nextcloud (not
    # Name=scottishwidow) and Song Vault is Name=song-vault. Exactly one instance matches.
    target_tags = {
      Name = var.next_cloud_instance_name
    }

    parameters {
      # The boot volume IS the data volume. Excluding it would back up nothing.
      exclude_boot_volume = false

      # Never reboot production to take a backup.
      no_reboot = true
    }

    schedule {
      name      = "daily"
      copy_tags = true

      create_rule {
        cron_expression = var.next_cloud_backup_daily_cron
      }

      retain_rule {
        count = var.next_cloud_backup_daily_count
      }

      tags_to_add = merge(var.tags, {
        Name     = "${var.next_cloud_instance_name}-backup"
        Schedule = "daily"
      })
    }

    schedule {
      name      = "weekly"
      copy_tags = true

      create_rule {
        cron_expression = var.next_cloud_backup_weekly_cron
      }

      retain_rule {
        count = var.next_cloud_backup_weekly_count
      }

      tags_to_add = merge(var.tags, {
        Name     = "${var.next_cloud_instance_name}-backup"
        Schedule = "weekly"
      })
    }

    schedule {
      name      = "monthly"
      copy_tags = true

      create_rule {
        cron_expression = var.next_cloud_backup_monthly_cron
      }

      retain_rule {
        count = var.next_cloud_backup_monthly_count
      }

      tags_to_add = merge(var.tags, {
        Name     = "${var.next_cloud_instance_name}-backup"
        Schedule = "monthly"
      })
    }
  }

  tags = var.tags
}
