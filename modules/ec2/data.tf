data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

data "aws_vpc" "main" {
  filter {
    name = "tag:env"
    values = [ "test-assignment" ]
  }
}

data "aws_subnet" "selected_public" {
  filter {
    name = "tag:EC2"
    values = ["true"]
  }
}