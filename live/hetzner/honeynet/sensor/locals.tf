locals {
  sensor_labels = merge(var.labels, { role = "sensor" })

  redirected_public_ports = [for public_port in keys(var.honeypot_port_redirects) : tonumber(public_port)]
  dnat_kept_ports         = setsubtract(var.honeypot_tcp_ports, local.redirected_public_ports)

  dnat_redirect_rules = [
    for public_port, honeypot_port in var.honeypot_port_redirects :
    "ip daddr $sensor_public_ipv4 tcp dport ${public_port} dnat to $honeypot:${honeypot_port}"
  ]
  dnat_kept_rules = length(local.dnat_kept_ports) == 0 ? [] : [
    "ip daddr $sensor_public_ipv4 tcp dport { ${join(", ", local.dnat_kept_ports)} } dnat to $honeypot"
  ]
  dnat_honeypot_rules = concat(local.dnat_redirect_rules, local.dnat_kept_rules)

  sinkhole_redirects = [
    { protocol = "tcp", port = 80, sinkhole_port = var.sinkhole_ports.http },
    { protocol = "tcp", port = 443, sinkhole_port = var.sinkhole_ports.https },
    { protocol = "udp", port = 53, sinkhole_port = var.sinkhole_ports.dns },
    { protocol = "tcp", port = 53, sinkhole_port = var.sinkhole_ports.dns },
  ]
  dnat_sinkhole_rules = [
    for redirect in local.sinkhole_redirects :
    "ip saddr $honeynet ip daddr != $honeynet ${redirect.protocol} dport ${redirect.port} dnat to $sensor_private_ip:${redirect.sinkhole_port}"
  ]
  sinkhole_input_rules = [
    for redirect in local.sinkhole_redirects :
    "ip saddr $honeynet ${redirect.protocol} dport ${redirect.sinkhole_port} accept"
  ]

  dnat_rules = join("\n", concat(local.dnat_honeypot_rules, local.dnat_sinkhole_rules))

  sensor_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    admin_ssh_public_key = data.hcloud_ssh_key.honeynet.public_key
    admin_ssh_port       = var.admin_ssh_port
    network_ip_range     = data.hcloud_network.honeynet.ip_range
    network_gateway_ip   = cidrhost(data.hcloud_network.honeynet.ip_range, 1)
    public_ipv4          = hcloud_primary_ip.sensor.ip_address
    sensor_private_ip    = var.sensor_private_ip
    honeypot_ip          = var.honeypot_1_private_ip
    dnat_rules           = local.dnat_rules
    sinkhole_input_rules = join("\n", local.sinkhole_input_rules)
    proxy_port           = var.proxy_port
  })
}
