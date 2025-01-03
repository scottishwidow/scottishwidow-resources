resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = {
    Public = false
  }
}

resource "aws_route" "public_route" {
  route_table_id = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public_zone-1" {
  subnet_id = aws_subnet.public_zone-1.id
  route_table_id = aws_route_table.public.id
}