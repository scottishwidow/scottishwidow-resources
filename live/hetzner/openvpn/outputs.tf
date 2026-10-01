output "gateway_public_ipv4" {
  value = hcloud_primary_ip.gateway.ip_address
}

output "gateway_private_ip" {
  value = module.gateway.private_ip
}

output "ansible_inventory" {
  value = {
    gateways = {
      hosts = {
        gateway = {
          ansible_host = hcloud_primary_ip.gateway.ip_address
        }
      }
      vars = {
        openvpn_port            = var.openvpn_port
        openvpn_public_address  = hcloud_primary_ip.gateway.ip_address
        openvpn_network_address = cidrhost(var.vpn_network_ip_range, 0)
        openvpn_network_netmask = cidrnetmask(var.vpn_network_ip_range)
        private_network_address = cidrhost(data.hcloud_network.private.ip_range, 0)
        private_network_netmask = cidrnetmask(data.hcloud_network.private.ip_range)
      }
    }
  }
}
