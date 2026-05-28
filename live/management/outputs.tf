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
