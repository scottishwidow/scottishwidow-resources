data "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 0 : 1
  url   = var.oidc_provider_url
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    sid = "AllowGitHubActionsAssumeRole"

    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_host}:aud"
      values   = var.oidc_client_id_list
    }

    condition {
      test     = "StringLike"
      variable = "${local.oidc_provider_host}:sub"
      values   = local.allowed_subjects
    }
  }
}

data "aws_iam_policy_document" "github_actions_permissions" {
  statement {
    sid       = "TerraformApplyPermissions"
    effect    = "Allow"
    actions   = var.permissions_policy_actions
    resources = ["*"]
  }
}