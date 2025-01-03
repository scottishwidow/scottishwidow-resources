terraform {
  backend "s3" {
    bucket = var.terraform_state_bucket_name
    key = "backend.tfstate"
    region = var.region
    dynamodb_table = var.terraform_state_lock
    encrypt = true
  }
}