output "aws_security_group" {
  value = aws_security_group.wordpress_sg.id
}

output "aws_instance_public_ip" {
  value = aws_instance.wordpress_host.public_ip
}