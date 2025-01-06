data "aws_subnet" "selected_one" {
  filter {
    name = "tag:Identifier"
    values = ["1"]
  }
}

data "aws_subnet" "selected_two" {
  filter {
    name = "tag:Identifier"
    values = ["2"]
  }
}

data "aws_vpc" "selected" {
  filter {
    name = "cidr-block"
    values = [ "172.16.0.0/16" ]
  }
}

data "aws_security_group" "wordpress_sg" {
  filter {
    name = "tag:RDS"
    values = [ "true" ]
  }
}