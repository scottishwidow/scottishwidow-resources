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
  description = "EC2 instance type for the Nextcloud server"
  type        = string
  default     = "t3g.nano"
}
