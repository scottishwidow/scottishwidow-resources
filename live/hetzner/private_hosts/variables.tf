variable "network_name" {
  description = "Name of the private network the Private Hosts are attached to"
  type        = string
  default     = "hetzner"
}

variable "ssh_key_name" {
  description = "Name of the Hetzner SSH key installed on the Private Hosts"
  type        = string
}

variable "location" {
  description = "Hetzner location of the Private Hosts. Must be in the network zone of the private network"
  type        = string
  default     = "fsn1"
}

variable "gateway_private_ip" {
  description = "Private IP of the Gateway. The only source allowed to open connections to the Private Hosts"
  type        = string
  default     = "10.10.0.2"
}

variable "network_gateway_ip" {
  description = "Gateway IP of the private network subnet. Hetzner reserves the first host address of the subnet for it"
  type        = string
  default     = "10.10.0.1"
}

variable "dns_servers" {
  description = "DNS resolvers of the Private Hosts"
  type        = list(string)
  default     = ["185.12.64.1", "185.12.64.2"]
}

variable "private_host_count" {
  description = "Number of identical Private Hosts. They are named private-1 to private-N"
  type        = number
  default     = 1

  validation {
    condition     = var.private_host_count >= 0 && floor(var.private_host_count) == var.private_host_count
    error_message = "private_host_count must be a whole number of 0 or more."
  }
}

variable "private_host_server_type" {
  description = "Hetzner server type of the Private Hosts"
  type        = string
  default     = "cx23"
}

variable "private_host_image" {
  description = "Image the Private Hosts are created from"
  type        = string
  default     = "ubuntu-24.04"
}

variable "labels" {
  description = "Labels applied to all Private Host resources"
  type        = map(string)
  default = {
    env        = "hetzner"
    management = "terraform"
  }
}
