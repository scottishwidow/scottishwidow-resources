data "hcloud_network" "private" {
  name = var.network_name
}

data "hcloud_ssh_key" "admin" {
  name = var.ssh_key_name
}
