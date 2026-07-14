resource "aws_iam_role" "this" {
  name               = "${var.name}-dlm-lifecycle"
  description        = "Assumed by Data Lifecycle Manager to snapshot the ${var.name} instance."
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = var.tags
}

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
