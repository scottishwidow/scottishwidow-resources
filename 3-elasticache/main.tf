module "aws_elasticache_cluster" {
  source = "../modules/elasticache"
}

terraform {
  backend "s3" {
    bucket = "tf-state-wordpress-test-assignment"
    key = "elasticache.tfstate"
    region = "eu-west-1"
    dynamodb_table = "tf-state-lock"
    encrypt = true
  }
}