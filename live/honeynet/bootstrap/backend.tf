terraform {
  backend "s3" {
    bucket       = "tf-state-scottishwidow-hetzner"
    key          = "honeynet/bootstrap/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
