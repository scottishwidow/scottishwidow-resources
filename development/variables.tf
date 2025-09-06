variable "aws_region" {
  type        = string
  description = "AWS Region to deploy to"
  default     = "eu-central-1"
}

variable "env" {
  description = "Deployment environment (dev, stage, prod)"
  type = string
  default = "dev"
}