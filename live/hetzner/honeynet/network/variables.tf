variable "network_name" {
  description = "Name of the Honeynet network"
  type        = string
  default     = "honeynet"
}

variable "network_ip_range" {
  description = "IP range of the Honeynet network"
  type        = string
  default     = "10.20.0.0/24"
}

variable "subnet_ip_range" {
  description = "IP range of the cloud subnet"
  type        = string
  default     = "10.20.0.0/24"
}

variable "network_zone" {
  description = "Hetzner network zone of the subnet"
  type        = string
  default     = "eu-central"
}

variable "sensor_private_ip" {
  description = "Fixed private IP of the Sensor. Must not be the subnet's first host address, which Hetzner reserves as the subnet gateway"
  type        = string
  default     = "10.20.0.2"
}

variable "labels" {
  description = "Labels applied to the network"
  type        = map(string)
  default = {
    env        = "honeynet"
    management = "terraform"
  }
}
