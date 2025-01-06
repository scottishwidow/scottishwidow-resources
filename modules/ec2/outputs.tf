output "aws_security_group" {
  value = aws_security_group.wordpress_sg.id # to be grabbed by RDS module for inbound 
}