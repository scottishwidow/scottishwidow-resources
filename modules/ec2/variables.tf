variable "region" {
  description = "AWS region for bootstrap"
  type = string
  default = "eu-west-1"
}

variable "key_name" {
  description = "Name of the SSH Key"
  type = string
  default = "k.michael"
}