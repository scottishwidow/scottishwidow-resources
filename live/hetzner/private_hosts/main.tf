module "private_host" {
  source   = "../../../modules/hcloud_server"
  for_each = var.private_hosts

  name        = each.key
  server_type = each.value.server_type
  image       = each.value.image
  location    = var.location
  ssh_key_ids = [data.hcloud_ssh_key.admin.id]
  network_id  = data.hcloud_network.private.id
  private_ip  = each.value.private_ip
  user_data   = local.private_host_user_data
  labels      = local.private_host_labels
}
