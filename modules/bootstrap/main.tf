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
      mode = "GOVERNANCE"
      days = 5
    }
  }
}

resource "aws_s3_bucket_policy" "terraform_state_bucket_tls_only" {
  bucket = aws_s3_bucket.terraform_state_bucket.id
  policy = data.aws_iam_policy_document.terraform_state_bucket_tls_only.json
}

data "aws_iam_policy_document" "terraform_state_bucket_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.terraform_state_bucket.arn,
      "${aws_s3_bucket.terraform_state_bucket.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_logging" "terraform_state_bucket" {
  depends_on = [aws_s3_bucket_policy.access_log_bucket]

  bucket        = aws_s3_bucket.terraform_state_bucket.id
  target_bucket = aws_s3_bucket.access_log_bucket.id
  target_prefix = "${aws_s3_bucket.terraform_state_bucket.id}/"
}

resource "aws_s3_bucket" "access_log_bucket" {
  bucket = "tf-state-access-logs-${local.environment_prefix}"
  tags   = var.tags
}

resource "aws_s3_bucket_ownership_controls" "access_log_bucket" {
  bucket = aws_s3_bucket.access_log_bucket.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "access_log_bucket" {
  bucket = aws_s3_bucket.access_log_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_log_bucket" {
  bucket = aws_s3_bucket.access_log_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_log_bucket" {
  bucket = aws_s3_bucket.access_log_bucket.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.access_log_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_policy" "access_log_bucket" {
  depends_on = [aws_s3_bucket_public_access_block.access_log_bucket]

  bucket = aws_s3_bucket.access_log_bucket.id
  policy = data.aws_iam_policy_document.access_log_bucket.json
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "access_log_bucket" {
  statement {
    sid       = "AllowStateBucketAccessLogDelivery"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.access_log_bucket.arn}/${aws_s3_bucket.terraform_state_bucket.id}/*"]

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.terraform_state_bucket.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.access_log_bucket.arn,
      "${aws_s3_bucket.access_log_bucket.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
