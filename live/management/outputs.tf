output "next_cloud_public_ip" {
  description = "Elastic IP address associated with the Nextcloud instance."
  value       = module.next_cloud.public_ip
}

output "next_cloud_domain" {
  description = "Public domain the Nextcloud A record should point at."
  value       = var.domain
}

output "ssm_scratch_bucket_name" {
  description = "Name of the S3 scratch bucket for the aws_ssm Ansible connection plugin."
  value       = module.ssm_scratch.s3_bucket_id
}

output "ssm_scratch_bucket_region" {
  description = "Region of the S3 scratch bucket."
  value       = module.ssm_scratch.s3_bucket_region
}
