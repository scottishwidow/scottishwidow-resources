module "vpc" {
  source = "../../modules/vpc"
  tags   = { environment = "management", management = "terraform", Name = "scottishwidow" }
  region = var.aws_region
}

# module "alb" {
#   source = "../../modules/alb"
#   tags = { environment = "management", management = "terraform" }
#   vpc_id = module.vpc.vpc_id
#   alb_subnets = [module.vpc.public_zone_1, module.vpc.public_zone_2]
#   env = var.env
#   alb_sg_name = "scottishwidow-alb-sg"
# }

# module "database" {
#   source = "../../modules/database"
#   postgres_instance_identifier = "scottishwidow-postgres"
#   subnet_ids = [ module.vpc.public_zone_1, module.vpc.private_zone_1 ]
#   tags = { environment = "management", management = "terraform" }
#   db_password_secret_name = "postgres_pwd_secret"
#   postgres_sg_name = "rds_postgres_sg"
#   vpc_id = module.vpc.vpc_id
# }

# module "docker_swarm" {
#   source = "../modules/docker-swarm"
#   region = var.aws_region
#   vpc_id = module.vpc.vpc_id
#   subnet_ids = [module.vpc.public_zone_1, module.vpc.public_zone_2]
#   key_name = var.key_name
#   instance_type = var.docker_swarm_instance_type
#   ec2_instance_name = "docker-swarm"
#   public_ip_associate = false
#   tags = { environment = "management", management = "terraform" }
# }
