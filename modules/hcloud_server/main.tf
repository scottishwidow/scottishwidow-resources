resource "hcloud_server" "this" {
  name         = var.name
  server_type  = var.server_type
  image        = var.image
  location     = var.location
  ssh_keys     = var.ssh_key_ids
  firewall_ids = var.firewall_ids
  labels       = var.labels
  user_data    = var.user_data

  public_net {
    ipv4_enabled = var.primary_ipv4_id != null
    ipv4         = var.primary_ipv4_id
    ipv6_enabled = false
  }

  network {
    network_id = var.network_id
    ip         = var.private_ip
    alias_ips  = []
  }
}
