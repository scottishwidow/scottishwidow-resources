# development

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 6.0 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| github\_actions\_iam | ../../modules/iam-github-oidc | n/a |
| vpc | terraform-aws-modules/vpc/aws | 6.6.0 |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| aws\_region | AWS Region to deploy to | `string` | `"eu-central-1"` | no |

## Outputs

| Name | Description |
|------|-------------|
| github\_actions\_oidc\_provider\_arn | n/a |
| github\_actions\_role\_arn | n/a |
<!-- END_TF_DOCS -->
