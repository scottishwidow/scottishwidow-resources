data "aws_subnet" "selected" {
  filter {
    name = "tag:RDS"
    values = ["true"]
  }
}

data "aws_vpc" "selected" {
  filter {
    name = "cidr-block"
    values = [ "172.16.0.0/16" ]
  }
}