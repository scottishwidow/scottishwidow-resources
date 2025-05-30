module "vpc" {
  source = "../modules/vpc"
  tags   = { environment = development, management = terraform }
  region = data.aws_region.current
}