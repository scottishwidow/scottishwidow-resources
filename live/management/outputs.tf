# Stable public address. Consumed by the out-of-band Route 53 step (A record
# domain -> this IP) and by Ansible/AIO as the host's reachable address.
output "next_cloud_public_ip" {
  description = "Elastic IP address associated with the Nextcloud instance."
  value       = module.next_cloud.public_ip
}

output "next_cloud_domain" {
  description = "Public domain the Nextcloud A record should point at."
  value       = var.domain
}

# Consumed by the Ansible layer to point the amazon.aws.aws_ssm connection
# plugin at its file-transfer side-channel. See ADR-0001.
output "ssm_scratch_bucket_name" {
  description = "Name of the S3 scratch bucket for the aws_ssm Ansible connection plugin."
  value       = module.ssm_scratch.s3_bucket_id
}

output "ssm_scratch_bucket_region" {
  description = "Region of the S3 scratch bucket."
  value       = module.ssm_scratch.s3_bucket_region
}
