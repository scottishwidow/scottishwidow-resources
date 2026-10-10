terraform {
  backend "s3" {
    bucket       = "tf-state-scottishwidow-hetzner"
    key          = "ovpn/private_hosts/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
