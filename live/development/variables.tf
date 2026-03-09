variable "aws_region" {
  type        = string
  description = "AWS Region to deploy to"
  default     = "eu-central-1"
}

# variable "github_actions_role_name" {
#   description = "IAM role name assumed by GitHub Actions for development applies"
#   type        = string
#   default     = "github-actions-terraform-development"
# }

# variable "github_actions_repository" {
#   description = "GitHub repository allowed to assume the development Terraform role"
#   type        = string
#   default     = "scottishwidow/scottishwidow-resources"
# }

# variable "github_actions_branches" {
#   description = "Git branches allowed to assume the development Terraform role"
#   type        = list(string)
#   default     = ["main"]
# }

# variable "create_github_oidc_provider" {
#   description = "Create GitHub OIDC provider in the current account"
#   type        = bool
#   default     = true
# }
