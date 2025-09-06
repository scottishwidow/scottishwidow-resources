module "vpc" {
  source = "../modules/vpc"
  tags   = { environment = "development", management = "terraform" }
  region = data.aws_region.current.name
}

module "database" {
  source = "../modules/database"
  postgres_instance_identifier = "scottishwidow-postgres"
  subnet_ids = [ module.vpc.public_zone-1, module.vpc.private_zone-1 ]
  tags = { environment = "development", management = "terraform" }
  db_password_secret_name = "postgres_pwd_secret"
  postgres_sg_name = "rds_postgres_sg"
  vpc_id = module.vpc.vpc_id
}