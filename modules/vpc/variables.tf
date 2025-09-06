variable "tags" {
  description = "VPC tags"
  type        = map(any)
}

variable "vpc_cidr_block" {
  description = "CIDR Block for VPC"
  type        = string
  default     = "172.16.0.0/16"
}

variable "public_subnet_cidr_block_1" {
  description = "CIDR Block for Public Subnet"
  type        = string
  default     = "172.16.128.0/19"
}

variable "public_subnet_cidr_block_2" {
  description = "CIDR Block for Public Subnet"
  type = string
  default = "172.16.160.0/19"
}

variable "private_subnet_cidr_block_1" {
  description = "CIDR Block for Private Subnet"
  type        = string
  default     = "172.16.192.0/19"
}

variable "private_subnet_cidr_block_2" {
  description = "CIDR Block for Private Subnet"
  type        = string
  default     = "172.16.224.0/19"
}

variable "az-1" {
  type        = string
  description = "Private AZ"
  default     = "eu-central-1a"
}

variable "az-2" {
  type        = string
  description = "Public AZ"
  default     = "eu-central-1b"
}

variable "region" {
  description = "AWS region for VPC"
  type        = string
}