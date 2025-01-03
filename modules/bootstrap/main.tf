resource "aws_s3_bucket" "terraform_state_bucket" {
  bucket = "tf-state-${local.environment_prefix}"
}