variable "network_name" {
  description = "Name of the Honeynet network the Sensor is attached to"
  type        = string
  default     = "honeynet"
}

variable "ssh_key_name" {
  description = "Name of the Honeynet SSH key installed for the admin user"
  type        = string
  default     = "honeynet"
}

variable "admin_cidrs" {
  description = "CIDRs allowed to reach the Sensor on admin SSH"
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0
    error_message = "admin_cidrs must contain at least one CIDR."
  }
}

variable "admin_ssh_port" {
  description = "Port of the real SSH server on the Sensor. Port 22 is kept free for the SSH honeypot"
  type        = number
  default     = 2222
}

variable "honeypot_1_private_ip" {
  description = "Private IP of honeypot-1. The Sensor forwards the honeypot ports to it. The Makefile sets it for the sensor and honeypots roots"
  type        = string

  validation {
    condition     = can(cidrhost("${var.honeypot_1_private_ip}/32", 0))
    error_message = "honeypot_1_private_ip must be an IPv4 address."
  }
}

variable "honeypot_tcp_ports" {
  description = "TCP ports that the Sensor accepts from anywhere and forwards to honeypot-1"
  type        = list(number)
  default     = [21, 22, 23, 80, 445, 1433, 3306]
}

variable "proxy_port" {
  description = "Port of the allowlist proxy on the Sensor. Only the Honeynet network can reach it"
  type        = number
  default     = 3128
}

variable "location" {
  description = "Hetzner location of the Sensor and its primary IPv4"
  type        = string
  default     = "fsn1"
}

variable "sensor_server_type" {
  description = "Hetzner server type of the Sensor"
  type        = string
  default     = "cx23"
}

variable "sensor_image" {
  description = "Image the Sensor is created from"
  type        = string
  default     = "ubuntu-24.04"
}

variable "sensor_private_ip" {
  description = "Fixed private IP of the Sensor. Must match the default route target of the network"
  type        = string
  default     = "10.20.0.2"
}

variable "labels" {
  description = "Labels applied to all Sensor resources"
  type        = map(string)
  default = {
    env        = "honeynet"
    management = "terraform"
  }
}
