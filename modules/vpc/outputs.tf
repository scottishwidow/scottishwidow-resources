output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_zone-1" {
  value = aws_subnet.public_zone-1.id
}

output "private_zone-1" {
  value = aws_subnet.private_zone-1.id
}