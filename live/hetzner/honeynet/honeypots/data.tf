data "hcloud_network" "honeynet" {
  name = var.network_name
}

data "hcloud_ssh_key" "honeynet" {
  name = var.ssh_key_name
}
