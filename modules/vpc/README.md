# vpc

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
| [aws_internet_gateway.igw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/internet_gateway) | resource |
| [aws_route.public_route](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route) | resource |
| [aws_route_table.private](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table) | resource |
| [aws_route_table.public](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table) | resource |
| [aws_route_table_association.private_zone_1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_route_table_association.private_zone_2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_route_table_association.public_zone_1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_route_table_association.public_zone_2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_subnet.private_zone_1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_subnet.private_zone_2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_subnet.public_zone_1](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_subnet.public_zone_2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_vpc.main](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| az\_1 | Private AZ | `string` | `"eu-central-1a"` | no |
| az\_2 | Public AZ | `string` | `"eu-central-1b"` | no |
| az\_3 | Public AZ | `string` | `"eu-central-1c"` | no |
| private\_subnet\_cidr\_block\_1 | CIDR Block for Private Subnet | `string` | `"172.16.192.0/19"` | no |
| private\_subnet\_cidr\_block\_2 | CIDR Block for Private Subnet | `string` | `"172.16.224.0/19"` | no |
| public\_subnet\_cidr\_block\_1 | CIDR Block for Public Subnet | `string` | `"172.16.128.0/19"` | no |
| public\_subnet\_cidr\_block\_2 | CIDR Block for Public Subnet | `string` | `"172.16.160.0/19"` | no |
| region | AWS region for VPC | `string` | n/a | yes |
| tags | VPC tags | `map(any)` | n/a | yes |
| vpc\_cidr\_block | CIDR Block for VPC | `string` | `"172.16.0.0/16"` | no |

## Outputs

| Name | Description |
|------|-------------|
| private\_zone\_1 | n/a |
| private\_zone\_2 | n/a |
| public\_zone\_1 | n/a |
| public\_zone\_2 | n/a |
| vpc\_id | n/a |
<!-- END_TF_DOCS -->
