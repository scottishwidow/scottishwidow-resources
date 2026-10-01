locals {
  gateway_labels = merge(var.labels, { role = "gateway" })

  gateway_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    private_network_ip_range = data.hcloud_network.private.ip_range
  })
}
