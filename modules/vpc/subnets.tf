resource "aws_subnet" "private_zone-1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr_block-1
  availability_zone = var.az-1

  tags = {
    availability = "private"
  }
}

resource "aws_subnet" "private_zone-2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr_block-2
  availability_zone = var.az-2

  tags = {
    availability = "private"
  }
}

resource "aws_subnet" "public_zone-1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr_block
  availability_zone       = var.az-2
  map_public_ip_on_launch = true

  tags = {
    availability = "public"
  }
}