variable "ssh_key_name" {
  description = "Name of the Hetzner SSH key for admin access to the project's servers"
  type        = string
}

variable "ssh_public_key_path" {
  description = "Local path to the public key uploaded as the Hetzner SSH key"
  type        = string
}
