module "honeypot" {
  source   = "../../../../modules/hcloud_server"
  for_each = local.honeypot_private_ips

  name        = each.key
  server_type = var.honeypot_server_type
  image       = var.honeypot_image
  location    = var.location
  ssh_key_ids = [data.hcloud_ssh_key.honeynet.id]
  network_id  = data.hcloud_network.honeynet.id
  private_ip  = each.value
  user_data   = local.honeypot_user_data
  labels      = local.honeypot_labels
}
