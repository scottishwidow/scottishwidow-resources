output "terraform_state_bucket_name" {
  value = module.bootstrap.terraform_state_bucket_name
}

output "terraform_state_lock" {
  value = module.bootstrap.aws_dynamodb_table.name
}