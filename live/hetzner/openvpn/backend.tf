terraform {
  backend "s3" {
    bucket       = "tf-state-scottishwidow-hetzner"
    key          = "openvpn/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
