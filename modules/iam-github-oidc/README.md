# iam-github-oidc

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 6.0 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 6.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_iam_openid_connect_provider.github](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_openid_connect_provider) | resource |
| [aws_iam_policy.github_actions_permissions](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy) | resource |
| [aws_iam_role.github_actions](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy_attachment.github_actions_permissions](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_iam_openid_connect_provider.github](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_openid_connect_provider) | data source |
| [aws_iam_policy_document.github_actions_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.github_actions_permissions](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| create\_oidc\_provider | Whether to create the GitHub OIDC provider in this account | `bool` | `true` | no |
| github\_branches | Branch names allowed to assume this role | `list(string)` | ```[ "main" ]``` | no |
| github\_environments | GitHub Environment names allowed to assume this role | `list(string)` | `[]` | no |
| github\_repository | GitHub repository in owner/repo format | `string` | n/a | yes |
| oidc\_client\_id\_list | Allowed OIDC audiences | `list(string)` | ```[ "sts.amazonaws.com" ]``` | no |
| oidc\_provider\_url | OIDC provider URL for GitHub Actions | `string` | `"https://token.actions.githubusercontent.com"` | no |
| oidc\_thumbprint\_list | GitHub OIDC certificate thumbprints | `list(string)` | ```[ "6938fd4d98bab03faadb97b34396831e3780aea1" ]``` | no |
| permissions\_policy\_actions | Allowed API actions for Terraform apply in this repository | `list(string)` | ```[ "ec2:*", "elasticloadbalancing:*", "iam:*", "rds:*", "s3:*", "secretsmanager:*" ]``` | no |
| permissions\_policy\_name | Optional IAM policy name; when empty, uses <role\_name>-permissions | `string` | `""` | no |
| role\_name | IAM role name for GitHub Actions Terraform applies | `string` | n/a | yes |
| tags | Tags to apply to IAM resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| oidc\_provider\_arn | n/a |
| permissions\_policy\_arn | n/a |
| role\_arn | n/a |
| role\_name | n/a |
<!-- END_TF_DOCS -->
