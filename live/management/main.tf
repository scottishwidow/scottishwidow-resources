module "vpc" {
  source = "../../modules/vpc"
  tags   = { environment = "management", management = "terraform", Name = "scottishwidow" }
  region = var.aws_region
}

module "docker_swarm" {
  source = "../../modules/docker-swarm"
  region = var.aws_region
  vpc_id = module.vpc.vpc_id
  subnet_ids = [module.vpc.public_zone_1, module.vpc.public_zone_2]
  key_name = var.key_name
  instance_type = var.docker_swarm_instance_type
  ec2_instance_name = "docker-swarm"
  public_ip_associate = false
  tags = { environment = "management", management = "terraform" }
}