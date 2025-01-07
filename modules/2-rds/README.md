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
| [aws_db_instance.rds_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance) | resource |
| [aws_db_subnet_group.rds_subnet_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_subnet_group) | resource |
| [aws_security_group.rds_security_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_security_group.wordpress_sg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/security_group) | data source |
| [aws_subnet.selected_one](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |
| [aws_subnet.selected_two](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |
| [aws_vpc.selected](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_db_name"></a> [db\_name](#input\_db\_name) | MySQL Database Name | `string` | `"wordpress_db"` | no |
| <a name="input_db_password"></a> [db\_password](#input\_db\_password) | Database Password | `string` | n/a | yes |
| <a name="input_db_username"></a> [db\_username](#input\_db\_username) | Database Username | `string` | n/a | yes |
| <a name="input_final_snapshot_identifier"></a> [final\_snapshot\_identifier](#input\_final\_snapshot\_identifier) | RDS Final Snapshot Identifier | `string` | `"final-snapshot"` | no |
| <a name="input_instance_identifier"></a> [instance\_identifier](#input\_instance\_identifier) | RDS Instance Identifier | `string` | `"rds-instance"` | no |
| <a name="input_mysql_engine_version"></a> [mysql\_engine\_version](#input\_mysql\_engine\_version) | MySQL Engine Version | `string` | `"8.4.3"` | no |
| <a name="input_region"></a> [region](#input\_region) | AWS Region for RDS | `string` | `"eu-west-1"` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | RDS Instance Tags | `map(any)` | n/a | yes |

## Outputs

No outputs.
<!-- END_TF_DOCS -->