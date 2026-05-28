module "vpc" {
  source = "../../modules/vpc"
  tags   = { environment = "management", management = "terraform", Name = "scottishwidow" }
  region = var.aws_region
}

module "next_cloud" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.0"

  name = var.next_cloud_instance_name

  ami                         = data.aws_ssm_parameter.ubuntu.value
  instance_type               = var.next_cloud_instance_type
  subnet_id                   = module.vpc.public_zone_1
  vpc_security_group_ids      = [module.next_cloud_sg.security_group_id]
  associate_public_ip_address = true

  # Bootstrap: update packages and install Docker Engine on first boot.
  # User data only runs once at launch, so changing the script must replace the
  # instance for the change to take effect.
  user_data                   = file("${path.module}/user_data.sh")
  user_data_replace_on_change = true

  # The AMI's default root volume is too small for the AIO container images,
  # data dir, and Postgres. Size it explicitly (~30 GB gp3). See ADR-0002.
  root_block_device = {
    type      = "gp3"
    size      = 30
    encrypted = true
  }

  # Create an instance profile and attach AmazonSSMManagedInstanceCore so
  # sessions open via Session Manager — no SSH key or inbound port 22 required.
  create_iam_instance_profile = true
  iam_role_description        = "Instance role for ${var.next_cloud_instance_name}: enables SSM Session Manager (no SSH)."
  iam_role_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  tags = {
    environment = "management"
    management  = "terraform"
    Name        = "scottishwidow"
  }

}

module "next_cloud_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.3"

  name        = "${var.next_cloud_instance_name}-sg"
  description = "Nextcloud instance: HTTP/HTTPS inbound only"
  vpc_id      = module.vpc.vpc_id

  ingress_cidr_blocks = var.ingress_cidr_blocks
  ingress_rules       = ["http-80-tcp", "https-443-tcp"]

  egress_rules = ["all-all"]

  tags = var.tags
}

