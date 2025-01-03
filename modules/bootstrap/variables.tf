variable "region" {
  description = "AWS region for bootstrap"
  type = string
  default = "eu-west-1"
}

variable "project_name" {
  type = string
  description = "Project name"
  default = "wordpress"
}

variable "env" {
  type = string
  description = "Environment name"
  default = "test-assignment"
}