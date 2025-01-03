variable "tags" {
  description = "VPC tags"
  type = map(any)
}

variable "cidr_block" {
  description = "CIDR Block for VPC"
  type = string
  default = "172.16.0.0/16"
}

variable "region" {
  description = "AWS region for VPC"
  type = string
  default = "eu-west-1"
}