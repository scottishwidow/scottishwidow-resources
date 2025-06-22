output "subnet_group_arn" {
  value = aws_db_subnet_group.postgres.arn
}

output "subnet_group_id" {
  value = aws_db_subnet_group.postgres.id
}

output "database_instance_id" {
  value = aws_db_instance.postgres.id
}