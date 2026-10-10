module "network" {
  source = "../../../../modules/hcloud_network"

  name               = var.network_name
  ip_range           = var.network_ip_range
  subnet_ip_range    = var.subnet_ip_range
  network_zone       = var.network_zone
  default_gateway_ip = var.sensor_private_ip
  labels             = var.labels
}
