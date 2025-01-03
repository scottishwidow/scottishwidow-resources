module "bootstrap" {
  source = "../modules/bootstrap"
  tags = { env = "test-assignment", management = "terraform" }
}