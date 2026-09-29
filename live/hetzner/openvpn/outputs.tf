output "gateway_public_ipv4" {
  value = hcloud_primary_ip.gateway.ip_address
}

output "gateway_private_ip" {
  value = module.gateway.private_ip
}
