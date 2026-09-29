output "network_id" {
  value = hcloud_network.this.id
}

output "subnet_id" {
  value = hcloud_network_subnet.cloud.id
}
