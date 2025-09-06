output "subnet_group_arn" {
  value =  var.create_postgres ? aws_db_subnet_group.postgres[0].arn : null
}

output "subnet_group_id" {
  value = var.create_postgres ? aws_db_subnet_group.postgres[0].id : null
}

output "database_instance_id" {
  value = var.create_postgres ? aws_db_instance.postgres[0].id : null
}