output "terraform_state_bucket_name" {
  value = module.bootstrap.terraform_state_bucket_name
}

output "ssh_key_name" {
  value = hcloud_ssh_key.admin.name
}
