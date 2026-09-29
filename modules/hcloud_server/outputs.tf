output "server_id" {
  value = hcloud_server.this.id
}

output "public_ipv4" {
  value = hcloud_server.this.ipv4_address
}

output "private_ip" {
  value = one(hcloud_server.this.network[*].ip)
}
