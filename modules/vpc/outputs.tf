output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_zone_1" {
  value = aws_subnet.public_zone_1.id
}

output "public_zone_2" {
  value = aws_subnet.public_zone_2.id
}

output "private_zone_1" {
  value = aws_subnet.private_zone_1.id
}

output "private_zone_2" {
  value = aws_subnet.private_zone_2.id
}