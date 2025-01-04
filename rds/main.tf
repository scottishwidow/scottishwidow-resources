module "rds" {
  source = "../modules/rds"
  tags = { env = "test-assignment", management = "terraform" }
  db_username = {}
  db_password = {}
}

terraform {
  backend "s3" {
    bucket = "tf-state-wordpress-test-assignment"
    key = "backend.tfstate"
    region = "eu-west-1"
    dynamodb_table = "tf-state-lock"
    encrypt = true
  }
}