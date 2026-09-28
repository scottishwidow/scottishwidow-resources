module "bootstrap" {
  source = "../../../modules/bootstrap"
  env    = "hetzner"
  tags   = { env = "hetzner", management = "bootstrap" }
}
