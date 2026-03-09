output "role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "role_name" {
  value = aws_iam_role.github_actions.name
}

output "permissions_policy_arn" {
  value = aws_iam_policy.github_actions_permissions.arn
}

output "oidc_provider_arn" {
  value = local.oidc_provider_arn
}
