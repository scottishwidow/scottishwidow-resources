data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server-minimal/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_vpc" "management" {
  tags = {
    Name = "scottishwidow"
    env  = "management"
  }
}

data "aws_subnet" "public_zone_1" {
  vpc_id     = data.aws_vpc.management.id
  cidr_block = "172.16.128.0/19"
}
