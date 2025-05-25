module "bootstrap" {
  source = "../modules/bootstrap"
  tags   = { env = "development", management = "terraform" }
}