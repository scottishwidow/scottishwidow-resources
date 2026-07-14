#########################
# Common
#########################

module "vpc" {
  source = "../../modules/vpc"
  tags   = { environment = "management", management = "terraform", Name = "scottishwidow" }
  region = var.aws_region
}

#########################
# Song Vault
#########################

module "song_vault" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.0"

  name = var.song_vault_instance_name

  ami                         = data.aws_ssm_parameter.ubuntu_amd64.value
  instance_type               = var.song_vault_instance_type
  subnet_id                   = module.vpc.public_zone_1
  vpc_security_group_ids      = [module.song_vault_sg.security_group_id]
  associate_public_ip_address = true

  ignore_ami_changes = true

  user_data                   = file("${path.module}/user_data_song_vault.sh")
  user_data_replace_on_change = true

  root_block_device = {
    type      = "gp3"
    size      = 10
    encrypted = true
  }

  create_iam_instance_profile = true
  iam_role_description        = "Instance role for ${var.song_vault_instance_name}: enables SSM Session Manager (no SSH)."
  iam_role_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  tags = {
    environment = "management"
    management  = "terraform"
    Name        = "scottishwidow"
  }
}

module "song_vault_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.3"

  name        = "${var.song_vault_instance_name}-sg"
  description = "Song Vault instance: HTTP/HTTPS inbound only"
  vpc_id      = module.vpc.vpc_id

  ingress_cidr_blocks = ["0.0.0.0/0"]
  ingress_rules       = ["http-80-tcp", "https-443-tcp"]

  egress_rules = ["all-all"]

  tags = var.tags
}

#########################
# Nextcloud
#########################

module "next_cloud" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.0"

  name = var.next_cloud_instance_name

  ami                         = data.aws_ssm_parameter.ubuntu.value
  instance_type               = var.next_cloud_instance_type
  subnet_id                   = module.vpc.public_zone_1
  vpc_security_group_ids      = [module.next_cloud_sg.security_group_id]
  associate_public_ip_address = true

  ignore_ami_changes = true

  user_data                   = file("${path.module}/user_data_next_cloud.sh")
  user_data_replace_on_change = true

  root_block_device = {
    type      = "gp3"
    size      = 30
    encrypted = true
  }

  create_eip = true
  eip_domain = "vpc"
  eip_tags   = { Name = var.next_cloud_instance_name }

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

  ingress_cidr_blocks = ["0.0.0.0/0"]
  ingress_rules       = ["http-80-tcp", "https-443-tcp"]

  egress_rules = ["all-all"]

  tags = var.tags
}

#########################
# Nextcloud backups
#########################

# All Nextcloud state — Postgres metadata and the file blobs alike — lives in Docker
# volumes on the instance's single root volume. One EBS snapshot therefore captures the
# database and the files at the same instant, which is what makes a restore coherent.
# Snapshots are crash-consistent, not application-quiesced: Postgres WAL-replays on
# restore exactly as it would after a power cut. See docs/adr/0003.
module "next_cloud_backup" {
  source = "../../modules/dlm_backup"

  name        = var.next_cloud_instance_name
  description = "Nextcloud EBS snapshots - ${join(" ", [for s in var.next_cloud_backup_schedules : "${s.retain_count} ${s.name}"])}"

  # The ec2-instance module's `name` argument wins over the `Name` key in `tags`, so the
  # instance is tagged Name=nextcloud (not Name=scottishwidow). Exactly one matches.
  target_tags = { Name = var.next_cloud_instance_name }
  schedules   = var.next_cloud_backup_schedules

  # The boot volume IS the data volume — excluding it would back up nothing.
  exclude_boot_volume = false
  no_reboot           = true

  snapshot_tags = var.tags
  tags          = var.tags
}

#########################
# SSM scratch bucket
#########################

module "ssm_scratch" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 5.13"

  bucket           = format("%s-%s-%s-an", var.ssm_scratch_bucket_prefix, data.aws_caller_identity.current.account_id, data.aws_region.current.region)
  bucket_namespace = "account-regional"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
      bucket_key_enabled = true
    }
  }

  lifecycle_rule = [
    {
      id      = "expire-scratch-objects"
      enabled = true
      filter  = {}

      expiration = {
        days = var.ssm_scratch_expiration_days
      }

      abort_incomplete_multipart_upload_days = var.ssm_scratch_expiration_days
    }
  ]

  tags = var.tags
}
