resource "hcloud_ssh_key" "honeynet" {
  name       = var.ssh_key_name
  public_key = file(pathexpand(var.ssh_public_key_path))
  labels     = { env = "honeynet", management = "bootstrap" }
}
