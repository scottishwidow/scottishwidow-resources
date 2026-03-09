# docker-swarm

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
| [aws_iam_instance_profile.swarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_instance_profile) | resource |
| [aws_iam_role.swarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy_attachment.swarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_instance.node](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance) | resource |
| [aws_security_group.swarm](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_security_group_rule.all_egress](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group_rule) | resource |
| [aws_security_group_rule.overlay_network](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group_rule) | resource |
| [aws_security_group_rule.swarm_manager](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group_rule) | resource |
| [aws_security_group_rule.swarm_node_tcp](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group_rule) | resource |
| [aws_security_group_rule.swarm_node_udp](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group_rule) | resource |
| [aws_ami.ubuntu](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_iam_policy_document.swarm_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| create\_instance\_profile | Create and attach an IAM instance profile for Swarm nodes | `bool` | `false` | no |
| ec2\_instance\_name | Name for the EC2 Instance | `string` | n/a | yes |
| instance\_count | Number of Docker Swarm nodes to create | `number` | `4` | no |
| instance\_profile\_policy\_arns | Policy ARNs to attach to the Swarm instance role | `list(string)` | ```[ "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" ]``` | no |
| instance\_type | Instance Type | `string` | n/a | yes |
| key\_name | Name of the SSH Key | `string` | n/a | yes |
| public\_ip\_associate | Boolean value that defines whether to assiciate a Public IP address | `bool` | n/a | yes |
| region | AWS Region to deploy to | `string` | n/a | yes |
| security\_group\_name | Name for the Docker Swarm security group | `string` | `"docker-swarm-sg"` | no |
| ssh\_cidr\_blocks | CIDR blocks allowed to reach SSH and Swarm ports | `list(string)` | ```[ "0.0.0.0/0" ]``` | no |
| subnet\_ids | Subnet IDs for the Docker Swarm nodes | `list(string)` | n/a | yes |
| tags | Project tags | `map(any)` | n/a | yes |
| vpc\_id | VPC ID for the Docker Swarm nodes | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| instance\_ids | n/a |
| private\_ips | n/a |
| public\_ips | n/a |
| security\_group\_id | n/a |
<!-- END_TF_DOCS -->
