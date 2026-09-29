variable "name" {
  description = "Name of the private network"
  type        = string
}

variable "ip_range" {
  description = "IP range of the private network in CIDR notation"
  type        = string
}

variable "subnet_ip_range" {
  description = "IP range of the cloud subnet in CIDR notation. Must be inside ip_range"
  type        = string
}

variable "network_zone" {
  description = "Hetzner network zone of the subnet"
  type        = string
  default     = "eu-central"
}

variable "default_gateway_ip" {
  description = "Private IP that receives all 0.0.0.0/0 traffic. No default route is created when null"
  type        = string
  default     = null
}

variable "labels" {
  description = "Labels applied to the network"
  type        = map(string)
  default     = {}
}
