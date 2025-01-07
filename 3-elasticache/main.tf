module "aws_elasticache_cluster" {
  source = "../modules/3-elasticache"
}

terraform {
  backend "s3" {
    bucket = "tf-state-wordpress-test-assignment../"../modules/3-elasticache".tfstate"
    region = "eu-west-1"
    dynamodb_table = "tf-state-lock"
    encrypt = true
  }
}