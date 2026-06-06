data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server-minimal/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id"
}

data "aws_ssm_parameter" "ubuntu_amd64" {
  name = "/aws/service/canonical/ubuntu/server-minimal/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
