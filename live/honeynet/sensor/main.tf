resource "hcloud_primary_ip" "sensor" {
  name              = "sensor-ipv4"
  type              = "ipv4"
  location          = var.location
  auto_delete       = false
  delete_protection = false
  labels            = local.sensor_labels
}

resource "hcloud_firewall" "sensor" {
  name   = "sensor"
  labels = local.sensor_labels

  rule {
    description = "Admin SSH from admin addresses"
    direction   = "in"
    protocol    = "tcp"
    port        = tostring(var.admin_ssh_port)
    source_ips  = var.admin_cidrs
  }
}

module "sensor" {
  source = "../../../modules/hcloud_server"

  name            = "sensor"
  server_type     = var.sensor_server_type
  image           = var.sensor_image
  location        = var.location
  ssh_key_ids     = [data.hcloud_ssh_key.honeynet.id]
  firewall_ids    = [hcloud_firewall.sensor.id]
  primary_ipv4_id = hcloud_primary_ip.sensor.id
  network_id      = data.hcloud_network.honeynet.id
  private_ip      = var.sensor_private_ip
  user_data       = local.sensor_user_data
  labels          = local.sensor_labels
}
