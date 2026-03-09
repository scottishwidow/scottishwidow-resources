module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.6.0"

  name = "development"
  cidr = "10.0.0.0/16"

  map_public_ip_on_launch = true

  azs             = ["eu-central-1a", "eu-central-1b", "eu-central-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]



  enable_nat_gateway = true
  enable_vpn_gateway = false

  tags = {
    management  = "terraform"
    environment = "development"
  }
}

module "github_actions_iam" {
  source = "../../modules/iam-github-oidc"

  role_name            = "github-actions-terraform-development"
  github_repository    = "scottishwidow/scottishwidow-resources"
  github_branches      = ["main"]
  create_oidc_provider = true
  tags = {
    management  = "terraform"
    environment = "development"
  }
}