output "terraform_state_bucket_name" {
  value = aws_s3_bucket.terraform_state_bucket.bucket_domain_name
}