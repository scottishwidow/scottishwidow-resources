output "github_actions_role_arn" {
  value = module.github_actions_iam.role_arn
}

output "github_actions_oidc_provider_arn" {
  value = module.github_actions_iam.oidc_provider_arn
}
