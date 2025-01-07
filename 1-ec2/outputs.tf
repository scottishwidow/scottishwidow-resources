output "public_ip" {
  value = module.ec2.aws_instance_public_ip
}