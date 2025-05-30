resource "aws_s3_bucket" "terraform_state_bucket" {
  bucket              = "tf-state-${local.environment_prefix}"
  object_lock_enabled = var.object_lock_enabled
  tags                = var.tags
}

resource "aws_s3_bucket_ownership_controls" "terraform_state_bucket_ownership" {
  bucket = aws_s3_bucket.terraform_state_bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "terraform_state_bucket_acl" {
  depends_on = [aws_s3_bucket_ownership_controls.terraform_state_bucket_ownership]

  bucket = aws_s3_bucket.terraform_state_bucket.id
  acl    = "private"
}

resource "aws_s3_bucket_versioning" "terraform_state_bucket_versioning" {
  bucket = aws_s3_bucket.terraform_state_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "terraform_state_bucket" {
  bucket = aws_s3_bucket.terraform_state_bucket.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 5
    }
  }
}
