data "hcloud_network" "honeynet" {
  name = var.network_name
}

data "hcloud_ssh_key" "honeynet" {
  name = var.ssh_key_name
}

data "hcloud_volume" "sensor_logs" {
  name = var.sensor_log_volume_name
}
