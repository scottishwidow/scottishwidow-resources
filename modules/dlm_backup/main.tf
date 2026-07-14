data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name}-dlm-lifecycle"
  description        = "Assumed by Data Lifecycle Manager to snapshot the ${var.name} instance."
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = var.tags
}

# No SSM permissions are attached: the policy runs no pre/post scripts. AWS ships no
# Linux app-consistent snapshot document (only Windows VSS and SAP HANA), and freezing
# the root filesystem risks deadlocking the agent meant to thaw it.
resource "aws_iam_role_policy_attachment" "this" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "this" {
  description        = var.description
  execution_role_arn = aws_iam_role.this.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["INSTANCE"]
    target_tags    = var.target_tags

    parameters {
      exclude_boot_volume = var.exclude_boot_volume
      no_reboot           = var.no_reboot
    }

    dynamic "schedule" {
      for_each = var.schedules

      content {
        name      = schedule.value.name
        copy_tags = true

        create_rule {
          cron_expression = schedule.value.cron_expression
        }

        retain_rule {
          count = schedule.value.retain_count
        }

        tags_to_add = merge(var.snapshot_tags, {
          Name     = "${var.name}-backup"
          Schedule = schedule.value.name
        })
      }
    }
  }

  tags = var.tags
}
