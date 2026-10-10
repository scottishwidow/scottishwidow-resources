locals {
  sensor_labels = merge(var.labels, { role = "sensor" })

  sensor_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    admin_ssh_public_key = data.hcloud_ssh_key.honeynet.public_key
    admin_ssh_port       = var.admin_ssh_port
  })
}
