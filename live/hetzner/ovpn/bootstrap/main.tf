module "bootstrap" {
  source = "../../../../modules/bootstrap"
  env    = "hetzner"
  tags   = { env = "hetzner", management = "bootstrap" }
}

resource "hcloud_ssh_key" "admin" {
  name       = var.ssh_key_name
  public_key = file(pathexpand(var.ssh_public_key_path))
  labels     = { env = "ovpn", management = "bootstrap" }
}
