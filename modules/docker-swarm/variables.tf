variable "region" {
  description = "AWS Region to deploy to"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for the Docker Swarm nodes"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the Docker Swarm nodes"
  type        = list(string)
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

variable "instance_count" {
  description = "Number of Docker Swarm nodes to create"
  type        = number
  default     = 4
}

variable "security_group_name" {
  description = "Name for the Docker Swarm security group"
  type        = string
  default     = "docker-swarm-sg"
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to reach SSH and Swarm ports"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "create_instance_profile" {
  description = "Create and attach an IAM instance profile for Swarm nodes"
  type        = bool
  default     = false
}

variable "instance_profile_policy_arns" {
  description = "Policy ARNs to attach to the Swarm instance role"
  type        = list(string)
  default     = ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
}
