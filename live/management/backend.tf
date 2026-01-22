terraform {
  backend "s3" {
    bucket       = "tf-state-scottishwidow-management"
    key          = "dev/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
