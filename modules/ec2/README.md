# ec2

<!-- BEGIN_TF_DOCS -->
## Requirements

No requirements.

## Providers

| Name | Version |
|------|---------|
| aws | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_instance.demo_host](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance) | resource |
| [aws_security_group.wordpress_sg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_ami.ubuntu](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| ec2\_instance\_name | Name for the EC2 Instance | `string` | n/a | yes |
| instance\_type | Instance Type | `string` | n/a | yes |
| key\_name | Name of the SSH Key | `string` | n/a | yes |
| public\_ip\_associate | Boolean value that defines whether to assiciate a Public IP address | `bool` | n/a | yes |
| region | AWS Region to deploy to | `string` | n/a | yes |
| tags | Project tags | `map(any)` | n/a | yes |

## Outputs

No outputs.
<!-- END_TF_DOCS -->
