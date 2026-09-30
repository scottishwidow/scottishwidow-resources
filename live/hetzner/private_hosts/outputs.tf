output "private_host_ips" {
  value = { for name, host in module.private_host : name => host.private_ip }
}
