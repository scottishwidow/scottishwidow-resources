output "sensor_public_ipv4" {
  value = hcloud_primary_ip.sensor.ip_address
}

output "sensor_private_ip" {
  value = module.sensor.private_ip
}

output "ansible_inventory" {
  value = {
    sensors = {
      hosts = {
        sensor = {
          ansible_host = hcloud_primary_ip.sensor.ip_address
          ansible_port = var.admin_ssh_port
        }
      }
      vars = {
        ssh_hardening_allow_tcp_forwarding = "local"
        honeynet_network_ip_range          = data.hcloud_network.honeynet.ip_range
        honeypot_1_private_ip              = var.honeypot_1_private_ip
      }
    }
  }
}
