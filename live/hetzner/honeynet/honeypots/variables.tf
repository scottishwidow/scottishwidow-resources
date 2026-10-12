variable "network_name" {
  description = "Name of the Honeynet network the Honeypots are attached to"
  type        = string
  default     = "honeynet"
}

variable "ssh_key_name" {
  description = "Name of the Honeynet SSH key installed for the admin user"
  type        = string
  default     = "honeynet"
}

variable "location" {
  description = "Hetzner location of the Honeypots. Must be in the network zone of the Honeynet network"
  type        = string
  default     = "fsn1"
}

variable "sensor_private_ip" {
  description = "Fixed private IP of the Sensor. The only source allowed to open SSH connections to the Honeypots"
  type        = string
  default     = "10.20.0.2"
}

variable "honeypot_1_private_ip" {
  description = "Private IP of honeypot-1. honeypot-N gets the Nth IP from it. The Makefile sets it for the sensor and honeypots roots"
  type        = string

  validation {
    condition     = can(cidrhost("${var.honeypot_1_private_ip}/32", 0))
    error_message = "honeypot_1_private_ip must be an IPv4 address."
  }
}

variable "honeypot_port_redirects" {
  description = "Public TCP ports that the Sensor forwards to another port on honeypot-1. Cowrie listens on the mapped ports. The Makefile sets it for the sensor and honeypots roots"
  type        = map(number)
  default = {
    22 = 2222
    23 = 2223
  }
}

variable "proxy_port" {
  description = "Port of the allowlist proxy on the Sensor. The Docker daemon and apt on every Honeypot use it. The Makefile sets it for the sensor and honeypots roots"
  type        = number
  default     = 3128
}

variable "honeypot_count" {
  description = "Number of identical Honeypots. They are named honeypot-1 to honeypot-N"
  type        = number
  default     = 1

  validation {
    condition     = var.honeypot_count >= 1 && floor(var.honeypot_count) == var.honeypot_count
    error_message = "honeypot_count must be a whole number of 1 or more."
  }
}

variable "honeypot_server_type" {
  description = "Hetzner server type of the Honeypots"
  type        = string
  default     = "cx23"
}

variable "honeypot_image" {
  description = "Image the Honeypots are created from"
  type        = string
  default     = "ubuntu-24.04"
}

variable "labels" {
  description = "Labels applied to all Honeypot resources"
  type        = map(string)
  default = {
    env        = "honeynet"
    management = "terraform"
  }
}
