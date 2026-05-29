#########################
# Common
#########################

variable "aws_region" {
  type        = string
  description = "AWS Region to deploy to"
  default     = "eu-central-1"
}

variable "env" {
  description = "Deployment environment (dev, stage, prod)"
  type        = string
  default     = "management"
}

variable "tags" {
  description = "Tags applied to all resources in this environment"
  type        = map(string)
  default = {
    environment = "management"
    management  = "terraform"
    Name        = "scottishwidow"
  }
}

#########################
# Nextcloud
#########################

variable "next_cloud_instance_name" {
  description = "Name tag for the Nextcloud EC2 instance"
  type        = string
  default     = "nextcloud"
}

variable "next_cloud_instance_type" {
  description = "EC2 instance type for the Nextcloud server (Graviton/arm64 — must match the arm64 AMI in data.tf)"
  type        = string
  default     = "t4g.small"
}

variable "domain" {
  description = "Public domain for the Nextcloud instance. Points at the Elastic IP via a Route 53 A record (created out-of-band; see CONTEXT.md) and is the name AIO requests a Let's Encrypt cert for. Set in secret.auto.tfvars."
  type        = string
}

#########################
# SSM scratch bucket
#########################

variable "ssm_scratch_bucket_prefix" {
  description = "Name prefix for the aws_ssm scratch bucket. The account ID, region, and `-an` namespace suffix are appended (final name: <prefix>-<account-id>-<region>-an)."
  type        = string
  default     = "scottishwidow-ssm-scratch"
}

variable "ssm_scratch_expiration_days" {
  description = "Days after which scratch-bucket objects (and stalled multipart uploads) are expired. Contents are transient transfer artifacts."
  type        = number
  default     = 1

  validation {
    condition     = var.ssm_scratch_expiration_days >= 1
    error_message = "Lifecycle expiration must be at least 1 day."
  }
}

