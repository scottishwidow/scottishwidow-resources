module "vpc" {
  source = "../modules/vpc"
  tags = { env = "test-assignment", management = "terraform" } 
}

terraform {
  backend "s3" {
    bucket = ""
    key = "backend.tfstate"
    region = "eu-west-1"
    dynamodb_table = ""
    encrypt = true
  }
}