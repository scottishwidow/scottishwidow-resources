locals {
  gateway_labels = merge(var.labels, { role = "gateway" })
}

resource "hcloud_primary_ip" "gateway" {
  name              = "gateway-ipv4"
  type              = "ipv4"
  location          = var.location
  auto_delete       = false
  delete_protection = true
  labels            = local.gateway_labels
}

resource "hcloud_firewall" "gateway" {
  name   = "gateway"
  labels = local.gateway_labels

  rule {
    description = "OpenVPN"
    direction   = "in"
    protocol    = "udp"
    port        = "1194"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "SSH from admin addresses"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.admin_cidrs
  }
}

module "gateway" {
  source = "../../../modules/hcloud_server"

  name            = "gateway"
  server_type     = var.gateway_server_type
  image           = var.gateway_image
  location        = var.location
  ssh_key_ids     = [data.hcloud_ssh_key.admin.id]
  firewall_ids    = [hcloud_firewall.gateway.id]
  primary_ipv4_id = hcloud_primary_ip.gateway.id
  network_id      = data.hcloud_network.private.id
  private_ip      = var.gateway_private_ip
  labels          = local.gateway_labels
}
