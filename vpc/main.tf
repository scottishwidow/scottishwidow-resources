module "vpc" {
  source = "../modules/vpc"
  tags = { env = "test-assignment", management = "terraform" } 
}

terraform {
  backend "s3" {
    bucket = "tf-state-wordpress-test-assignment"
    key = "vpc.tfstate"
    region = "eu-west-1"
    dynamodb_table = "tf-state-lock"
    encrypt = true
  }
}
