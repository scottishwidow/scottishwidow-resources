module "vpc" {
  source = "../modules/vpc"
  tags   = { environment = "development", management = "terraform", Name = "scottishwidow" }
  region = var.aws_region
}

module "alb" {
  source = "../modules/alb"
  tags = { environment = "development", management = "terraform" }
  vpc_id = module.vpc.vpc_id
  alb_subnets = [module.vpc.public_zone_1, module.vpc.public_zone_2]
  env = var.env
  alb_sg_name = "scottishwidow-alb-sg"
}

module "database" {
  source = "../modules/database"
  postgres_instance_identifier = "scottishwidow-postgres"
  subnet_ids = [ module.vpc.public_zone_1, module.vpc.private_zone_1 ]
  tags = { environment = "development", management = "terraform" }
  db_password_secret_name = "postgres_pwd_secret"
  postgres_sg_name = "rds_postgres_sg"
  vpc_id = module.vpc.vpc_id
}