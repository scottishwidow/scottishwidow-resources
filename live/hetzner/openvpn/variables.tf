variable "network_name" {
  description = "Name of the private network the Gateway is attached to"
  type        = string
  default     = "hetzner"
}

variable "ssh_key_name" {
  description = "Name of the Hetzner SSH key installed on the Gateway"
  type        = string
}

variable "admin_cidrs" {
  description = "CIDRs allowed to reach the Gateway on SSH"
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0
    error_message = "admin_cidrs must contain at least one CIDR."
  }
}

variable "location" {
  description = "Hetzner location of the Gateway and its primary IPv4"
  type        = string
  default     = "fsn1"
}

variable "gateway_server_type" {
  description = "Hetzner server type of the Gateway"
  type        = string
  default     = "cx23"
}

variable "gateway_image" {
  description = "Image the Gateway is created from"
  type        = string
  default     = "ubuntu-24.04"
}

variable "gateway_private_ip" {
  description = "Fixed private IP of the Gateway. Must match the default route target of the network"
  type        = string
  default     = "10.10.0.2"
}

variable "labels" {
  description = "Labels applied to all Gateway resources"
  type        = map(string)
  default = {
    env        = "hetzner"
    management = "terraform"
  }
}
