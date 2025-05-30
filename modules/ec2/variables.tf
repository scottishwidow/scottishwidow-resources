variable "region" {
  description = "AWS Region to deploy to"
  type        = string
}

variable "key_name" {
  description = "Name of the SSH Key"
  type        = string
}

variable "tags" {
  description = "Project tags"
  type        = map(any)
}

variable "instance_type" {
  description = "Instance Type"
  type        = string
}

variable "public_ip_associate" {
  description = "Boolean value that defines whether to assiciate a Public IP address"
  type        = bool
}

variable "ec2_instance_name" {
  description = "Name for the EC2 Instance"
  type        = string
}