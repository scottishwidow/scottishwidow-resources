module "vpc" {
  source = "../../../../modules/vpc"
  tags   = { env = "management", management = "terraform", Name = "scottishwidow" }
  region = var.aws_region
}
