variable "name" {
  description = "Name of the server"
  type        = string
}

variable "server_type" {
  description = "Hetzner server type"
  type        = string
}

variable "image" {
  description = "Image the server is created from"
  type        = string
}

variable "location" {
  description = "Hetzner location of the server. Must match the location of the primary IPv4"
  type        = string
}

variable "ssh_key_ids" {
  description = "IDs of the SSH keys installed for root"
  type        = list(string)
  default     = []
}

variable "firewall_ids" {
  description = "IDs of the firewalls applied to the server"
  type        = list(number)
  default     = []
}

variable "primary_ipv4_id" {
  description = "ID of the primary IPv4 assigned to the server. The server has no public IPv4 when null"
  type        = number
  default     = null
}

variable "network_id" {
  description = "ID of the private network the server is attached to"
  type        = number
}

variable "private_ip" {
  description = "Fixed IP of the server in the private network. Hetzner picks a free IP when null"
  type        = string
  default     = null
}

variable "labels" {
  description = "Labels applied to the server"
  type        = map(string)
  default     = {}
}
