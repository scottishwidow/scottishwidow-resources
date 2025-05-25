resource "aws_security_group" "wordpress_sg" {
  name        = "wordpress_security_group"
  description = "Security Group for Wordpress Host"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    RDS = true
  }
}

resource "aws_iam_role" "wordpress_ssm_role" {
  name = "wordpress_ssm_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ec2.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_policy" "wordpress_ssm_policy" {
  name        = "wordpress_ssm_policy"
  description = "Policy to allow access to SSM parameters for WordPress"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ],
        Resource = [
          "arn:aws:ssm:eu-west-1:975049889162:parameter/DB_HOST",
          "arn:aws:ssm:eu-west-1:975049889162:parameter/DB_NAME",
          "arn:aws:ssm:eu-west-1:975049889162:parameter/DB_PASSWORD",
          "arn:aws:ssm:eu-west-1:975049889162:parameter/DB_USER"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "wordpress_ssm_policy_attachment" {
  role       = aws_iam_role.wordpress_ssm_role.name
  policy_arn = aws_iam_policy.wordpress_ssm_policy.arn
}

resource "aws_iam_instance_profile" "wordpress_ssm_profile" {
  name = "wordpress_ssm_profile"
  role = aws_iam_role.wordpress_ssm_role.name
}

resource "aws_instance" "wordpress_host" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.micro"
  associate_public_ip_address = true
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

