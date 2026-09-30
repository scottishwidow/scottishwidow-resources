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

variable "private_hosts" {
  description = "Private Hosts keyed by server name. Hetzner picks a free private IP when private_ip is null"
  type = map(object({
    server_type = optional(string, "cx23")
    image       = optional(string, "ubuntu-24.04")
    private_ip  = optional(string)
  }))

  validation {
    condition = alltrue([
      for host in values(var.private_hosts) : host.private_ip != var.gateway_private_ip
    ])
    error_message = "A Private Host must not use the private IP of the Gateway."
  }
}

variable "labels" {
  description = "Labels applied to all Private Host resources"
  type        = map(string)
  default = {
    env        = "hetzner"
    management = "terraform"
  }
}
