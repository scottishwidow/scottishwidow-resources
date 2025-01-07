module "rds" {
  source = "../modules/2-rds"
  tags = { env = "test-assignment", management = "terraform" }
  db_username = var.db_username
  db_password = var.db_password
}

terraform {
  backend "s3" {
    bucket = "tf-state-wordpress-test-assignment"
    key = "rds.tfstate"
    region = "eu-west-1"
    dynamodb_table = "tf-state-lock"
    encrypt = true
  }
}
