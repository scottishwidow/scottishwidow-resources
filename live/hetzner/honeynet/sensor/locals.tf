locals {
  sensor_labels = merge(var.labels, { role = "sensor" })

  sensor_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    admin_ssh_public_key = data.hcloud_ssh_key.honeynet.public_key
    admin_ssh_port       = var.admin_ssh_port
    network_ip_range     = data.hcloud_network.honeynet.ip_range
    public_ipv4          = hcloud_primary_ip.sensor.ip_address
    honeypot_ip          = var.honeypot_1_private_ip
    honeypot_tcp_ports   = var.honeypot_tcp_ports
    proxy_port           = var.proxy_port
  })
}
