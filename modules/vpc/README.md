<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.10.1 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | ~> 5.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_internet_gateway.igw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/internet_gateway) | resource |
| [aws_route.public_route](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route) | resource |
| [aws_route_table.public](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table) | resource |
| [aws_route_table_association.public_zone-1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_subnet.private_zone-1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_subnet.private_zone-2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_subnet.public_zone-1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_vpc.main](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_az-1"></a> [az-1](#input\_az-1) | Private AZ | `string` | `"eu-west-1a"` | no |
| <a name="input_az-2"></a> [az-2](#input\_az-2) | Public AZ | `string` | `"eu-west-1b"` | no |
| <a name="input_private_subnet_cidr_block-1"></a> [private\_subnet\_cidr\_block-1](#input\_private\_subnet\_cidr\_block-1) | CIDR Block for Private Subnet | `string` | `"172.16.32.0/19"` | no |
| <a name="input_private_subnet_cidr_block-2"></a> [private\_subnet\_cidr\_block-2](#input\_private\_subnet\_cidr\_block-2) | CIDR Block for Private Subnet | `string` | `"172.16.64.0/19"` | no |
| <a name="input_public_subnet_cidr_block"></a> [public\_subnet\_cidr\_block](#input\_public\_subnet\_cidr\_block) | CIDR Block for Public Subnet | `string` | `"172.16.0.0/19"` | no |
| <a name="input_region"></a> [region](#input\_region) | AWS region for VPC | `string` | `"eu-west-1"` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | VPC tags | `map(any)` | n/a | yes |
| <a name="input_vpc_cidr_block"></a> [vpc\_cidr\_block](#input\_vpc\_cidr\_block) | CIDR Block for VPC | `string` | `"172.16.0.0/16"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_private_zone-1"></a> [private\_zone-1](#output\_private\_zone-1) | n/a |
| <a name="output_private_zone-2"></a> [private\_zone-2](#output\_private\_zone-2) | n/a |
| <a name="output_public_zone-1"></a> [public\_zone-1](#output\_public\_zone-1) | n/a |
| <a name="output_vpc_id"></a> [vpc\_id](#output\_vpc\_id) | n/a |
<!-- END_TF_DOCS -->
