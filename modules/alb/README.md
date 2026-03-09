# alb

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
| [aws_lb.alb](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb) | resource |
| [aws_security_group.alb_sg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| alb\_cross\_zone\_load\_balancing | Used to enable / disable cross zone load balancing for the ALB | `bool` | `false` | no |
| alb\_deletion\_protection | Used to enable / disable deletion protection for the ALB | `bool` | `false` | no |
| alb\_idle\_timeout | Time in seconds that the connection is allowed to be idle | `number` | `60` | no |
| alb\_name | Name of the ALB | `string` | `"scottishwidow"` | no |
| alb\_sg\_name | Name of the Security Group associated with the ALB | `any` | n/a | yes |
| alb\_subnets | List of subnet IDs where the Application Load Balancer will be deployed | `list(string)` | n/a | yes |
| env | Deployment environment prefix (dev, stage, prod) | `string` | n/a | yes |
| tags | Common tags to apply to all ALB resources | `map(string)` | n/a | yes |
| vpc\_id | ID of the VPC where ALB resources are deployed | `string` | n/a | yes |

## Outputs

No outputs.
<!-- END_TF_DOCS -->
