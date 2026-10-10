locals {
  honeypot_labels = merge(var.labels, { role = "honeypot" })

  network_octets    = [for octet in split(".", cidrhost(data.hcloud_network.honeynet.ip_range, 0)) : tonumber(octet)]
  honeypot_1_octets = [for octet in split(".", var.honeypot_1_private_ip) : tonumber(octet)]
  honeypot_1_host_number = sum([
    for index in range(4) : (local.honeypot_1_octets[index] - local.network_octets[index]) * pow(256, 3 - index)
  ])

  honeypot_private_ips = {
    for index in range(var.honeypot_count) :
    "honeypot-${index + 1}" => cidrhost(data.hcloud_network.honeynet.ip_range, local.honeypot_1_host_number + index)
  }

  honeypot_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    admin_ssh_public_key = data.hcloud_ssh_key.honeynet.public_key
    sensor_private_ip    = var.sensor_private_ip
    network_gateway_ip   = cidrhost(data.hcloud_network.honeynet.ip_range, 1)
  })
}
