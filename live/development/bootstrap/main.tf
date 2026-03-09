module "bootstrap" {
  source = "../../../modules/bootstrap"
  env = "development"
  tags   = { env = "development", management = "bootstrap" }
}
