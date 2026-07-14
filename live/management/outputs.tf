#########################
# Song Vault
#########################

output "song_vault_public_ip" {
  description = "Public IP address associated with the Song Vault instance."
  value       = module.song_vault.public_ip
}

#########################
# Nextcloud
#########################

output "next_cloud_public_ip" {
  description = "Elastic IP address associated with the Nextcloud instance."
  value       = module.next_cloud.public_ip
}

output "next_cloud_domain" {
  description = "Public domain the Nextcloud A record should point at."
  value       = var.domain
}

output "next_cloud_backup_policy_id" {
  description = "ID of the DLM lifecycle policy taking Nextcloud EBS snapshots. Inspect with: aws dlm get-lifecycle-policy --policy-id <id>."
  value       = module.next_cloud_backup.policy_id
}

#########################
# SSM scratch bucket
#########################

output "ssm_scratch_bucket_name" {
  description = "Name of the S3 scratch bucket for the aws_ssm Ansible connection plugin."
  value       = module.ssm_scratch.s3_bucket_id
}

output "ssm_scratch_bucket_region" {
  description = "Region of the S3 scratch bucket."
  value       = module.ssm_scratch.s3_bucket_region
}
