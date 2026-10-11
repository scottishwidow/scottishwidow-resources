output "honeypot_private_ips" {
  value = { for name, honeypot in module.honeypot : name => honeypot.private_ip }
}

output "ansible_inventory" {
  value = {
    honeypots = {
      hosts = {
        for name, honeypot in module.honeypot : name => {
          ansible_host = honeypot.private_ip
        }
      }
      vars = {
        ssh_hardening_allow_users = ["admin@${var.sensor_private_ip}"]
        sensor_private_ip         = var.sensor_private_ip
      }
    }
  }
}
