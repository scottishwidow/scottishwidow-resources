resource "aws_security_group" "wordpress_sg" {
  name        = "wordpress_security_group"
  description = "Security Group for Wordpress Host"
  vpc_id      = data.aws_vpc.main.id
}



resource "aws_instance" "demo_host" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  associate_public_ip_address = var.public_ip_associate
  key_name                    = var.key_name
  security_groups             = [aws_security_group.wordpress_sg.id]
  subnet_id                   = data.aws_subnet.selected_public.id

  root_block_device {
    volume_size = 15
    volume_type = "gp3"
  }

  iam_instance_profile = aws_iam_instance_profile.wordpress_ssm_profile.name

  user_data = file("${path.module}/user-data.sh")

  tags = var.tags
}

