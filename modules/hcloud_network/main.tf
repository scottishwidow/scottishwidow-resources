resource "hcloud_network" "this" {
  name     = var.name
  ip_range = var.ip_range
  labels   = var.labels
}

resource "hcloud_network_subnet" "cloud" {
  network_id   = hcloud_network.this.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = var.subnet_ip_range
}

resource "hcloud_network_route" "default" {
  count = var.default_gateway_ip == null ? 0 : 1

  network_id  = hcloud_network.this.id
  destination = "0.0.0.0/0"
  gateway     = var.default_gateway_ip

  depends_on = [hcloud_network_subnet.cloud]
}
