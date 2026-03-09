locals {
  oidc_provider_arn            = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
  oidc_provider_host           = trimsuffix(trimprefix(var.oidc_provider_url, "https://"), "/")
  allowed_branch_subjects      = [for branch in var.github_branches : "repo:${var.github_repository}:ref:refs/heads/${branch}"]
  allowed_environment_subjects = [for environment in var.github_environments : "repo:${var.github_repository}:environment:${environment}"]
  allowed_subjects             = distinct(concat(local.allowed_branch_subjects, local.allowed_environment_subjects))
  policy_name                  = var.permissions_policy_name != "" ? var.permissions_policy_name : "${var.role_name}-permissions"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url             = var.oidc_provider_url
  client_id_list  = var.oidc_client_id_list
  thumbprint_list = var.oidc_thumbprint_list

  tags = var.tags
}

resource "aws_iam_role" "github_actions" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json

  tags = var.tags
}

resource "aws_iam_policy" "github_actions_permissions" {
  name   = local.policy_name
  policy = data.aws_iam_policy_document.github_actions_permissions.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "github_actions_permissions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_permissions.arn
}
