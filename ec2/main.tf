module "ec2" {
  source = "../modules/ec2"
  tags = { env = "test-assignment", management = "terraform" }
}

terraform {
  backend "s3" {
    bucket = "tf-state-wordpress-test-assignment"
    key = "ec2.tfstate"
    region = "eu-west-1"
    dynamodb_table = "tf-state-lock"
    encrypt = true
  }
}