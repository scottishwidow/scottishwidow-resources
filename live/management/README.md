# management

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
| docker\_swarm | ../../modules/docker-swarm | n/a |
| vpc | ../../modules/vpc | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| aws\_region | AWS Region to deploy to | `string` | `"eu-central-1"` | no |
| docker\_swarm\_instance\_type | Instance type for Docker Swarm nodes | `string` | n/a | yes |
| env | Deployment environment (dev, stage, prod) | `string` | `"management"` | no |
| key\_name | Name of the SSH Key | `string` | n/a | yes |

## Outputs

No outputs.
<!-- END_TF_DOCS -->
