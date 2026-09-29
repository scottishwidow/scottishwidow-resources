variable "network_name" {
  description = "Name of the private network"
  type        = string
  default     = "hetzner"
}

variable "network_ip_range" {
  description = "IP range of the private network"
  type        = string
  default     = "10.10.0.0/24"
}

variable "subnet_ip_range" {
  description = "IP range of the cloud subnet"
  type        = string
  default     = "10.10.0.0/24"
}

variable "network_zone" {
  description = "Hetzner network zone of the subnet"
  type        = string
  default     = "eu-central"
}

variable "gateway_private_ip" {
  description = "Fixed private IP of the Gateway. Hetzner reserves the first host address of the subnet"
  type        = string
  default     = "10.10.0.2"
}

variable "labels" {
  description = "Labels applied to the network"
  type        = map(string)
  default = {
    env        = "hetzner"
    management = "terraform"
  }
}
