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

#########################
# Docker Swarm
#########################

variable "key_name" {
  description = "Name of the SSH Key"
  type        = string
}

variable "docker_swarm_instance_type" {
  description = "Instance type for Docker Swarm nodes"
  type        = string
}
