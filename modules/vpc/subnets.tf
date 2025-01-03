resource "aws_subnet" "private_zone-1" {
  vpc_id = aws_vpc.main.id
  cidr_block = var.private_subnet_cidr_block
  availability_zone = var.az-1

  tags = {
    RDS = true
  }
}

resource "aws_subnet" "public_zone-1" {
  vpc_id = aws_vpc.main.id
  cidr_block = var.public_subnet_cidr_block
  availability_zone = var.az-2
  map_public_ip_on_launch = true
}