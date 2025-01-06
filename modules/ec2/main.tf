resource "aws_security_group" "wordpress_sg" {
  name = "wordpress_security_group"
  description = "Security Group for Wordpress Host"
  vpc_id = data.terraform_remote_state.vpc.outputs.vpc_id[0]

  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "wordpress_host" {
  ami = data.aws_ami.ubuntu.id
  instance_type = "t2.micro"
  associate_public_ip_address = true
  key_name = var.key_name
  security_groups = [ aws_security_group.wordpress_sg.name ]

  root_block_device {
    volume_size = 15
    volume_type = "gp3"
  }
}