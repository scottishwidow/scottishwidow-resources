module "vpc" {
  source = "../modules/vpc"
  tags = { env = "test-assignment", management = "terraform" } 
}