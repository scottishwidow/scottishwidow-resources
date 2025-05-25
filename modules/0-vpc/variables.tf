variable "tags" {
  description = "VPC tags"
  type        = map(any)
}

variable "vpc_cidr_block" {
  description = "CIDR Block for VPC"
  type        = string
  default     = "172.16.0.0/16"
}

variable "public_subnet_cidr_block" {
  description = "CIDR Block for Public Subnet"
  type        = string
  default     = "172.16.0.0/19"
}

variable "private_subnet_cidr_block-1" {
  description = "CIDR Block for Private Subnet"
  type        = string
  default     = "172.16.32.0/19"
}

variable "private_subnet_cidr_block-2" {
  description = "CIDR Block for Private Subnet"
  type        = string
  default     = "172.16.64.0/19"
}

variable "az-1" {
  type        = string
  description = "Private AZ"
  default     = "eu-west-1a"
}

variable "az-2" {
  type        = string
  description = "Public AZ"
  default     = "eu-west-1b"
}

variable "region" {
  description = "AWS region for VPC"
  type        = string
  default     = "eu-west-1"
}

