module "private_host" {
  source   = "../../../../modules/hcloud_server"
  for_each = local.private_host_names

  name        = each.key
  server_type = var.private_host_server_type
  image       = var.private_host_image
  location    = var.location
  ssh_key_ids = [data.hcloud_ssh_key.admin.id]
  network_id  = data.hcloud_network.private.id
  user_data   = local.private_host_user_data
  labels      = local.private_host_labels
}
