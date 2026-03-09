module "bootstrap" {
  source = "../../../modules/bootstrap"
  env = "management"
  tags   = { env = "management", management = "bootstrap" }
}
