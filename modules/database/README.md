# database

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
| [aws_db_instance.postgres](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance) | resource |
| [aws_db_subnet_group.postgres](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_subnet_group) | resource |
| [aws_secretsmanager_secret.db_password](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret) | resource |
| [aws_secretsmanager_secret_version.db_password](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret_version) | resource |
| [aws_security_group.postgres](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| create\_postgres | n/a | `bool` | `false` | no |
| db\_password\_secret\_name | n/a | `string` | n/a | yes |
| is\_public | n/a | `bool` | `true` | no |
| postgres\_az | n/a | `string` | `"eu-central-1b"` | no |
| postgres\_instance\_class | n/a | `string` | `"db.t3.micro"` | no |
| postgres\_instance\_identifier | n/a | `string` | n/a | yes |
| postgres\_sg\_name | Name for AWS Security Group for Postgres RDS | `string` | n/a | yes |
| postgres\_skip\_final\_snapshot | n/a | `bool` | `true` | no |
| postgres\_storage | n/a | `number` | `10` | no |
| postgres\_username | n/a | `string` | `"postgres"` | no |
| subnet\_ids | n/a | `list(string)` | n/a | yes |
| tags | n/a | `map(string)` | n/a | yes |
| vpc\_id | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| database\_instance\_id | n/a |
| subnet\_group\_arn | n/a |
| subnet\_group\_id | n/a |
<!-- END_TF_DOCS -->
