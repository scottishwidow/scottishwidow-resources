variable "role_name" {
  description = "IAM role name for GitHub Actions Terraform applies"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in owner/repo format"
  type        = string

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository must be in owner/repo format."
  }
}

variable "github_branches" {
  description = "Branch names allowed to assume this role"
  type        = list(string)
  default     = ["main"]

  validation {
    condition     = length(var.github_branches) > 0 || length(var.github_environments) > 0
    error_message = "At least one of github_branches or github_environments must be configured."
  }
}

variable "github_environments" {
  description = "GitHub Environment names allowed to assume this role"
  type        = list(string)
  default     = []
}

variable "permissions_policy_name" {
  description = "Optional IAM policy name; when empty, uses <role_name>-permissions"
  type        = string
  default     = ""
}

variable "permissions_policy_actions" {
  description = "Allowed API actions for Terraform apply in this repository"
  type        = list(string)
  default = [
    "ec2:*",
    "elasticloadbalancing:*",
    "iam:*",
    "rds:*",
    "s3:*",
    "secretsmanager:*"
  ]

  validation {
    condition     = length(var.permissions_policy_actions) > 0
    error_message = "permissions_policy_actions must contain at least one IAM action."
  }
}

variable "create_oidc_provider" {
  description = "Whether to create the GitHub OIDC provider in this account"
  type        = bool
  default     = true
}

variable "oidc_provider_url" {
  description = "OIDC provider URL for GitHub Actions"
  type        = string
  default     = "https://token.actions.githubusercontent.com"
}

variable "oidc_client_id_list" {
  description = "Allowed OIDC audiences"
  type        = list(string)
  default     = ["sts.amazonaws.com"]
}

variable "oidc_thumbprint_list" {
  description = "GitHub OIDC certificate thumbprints"
  type        = list(string)
  default     = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

variable "tags" {
  description = "Tags to apply to IAM resources"
  type        = map(string)
  default     = {}
}
