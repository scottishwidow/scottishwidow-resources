locals {
  private_host_labels = merge(var.labels, { role = "private-host" })

  private_host_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    gateway_private_ip = var.gateway_private_ip
  })
}
