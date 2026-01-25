resource "aws_security_group" "swarm" {
  name        = var.security_group_name
  description = "Security group for Docker Swarm nodes"
  vpc_id      = var.vpc_id

  tags = var.tags
}

resource "aws_security_group_rule" "swarm_manager" {
  type              = "ingress"
  security_group_id = aws_security_group.swarm.id
  description       = "Swarm manager"
  from_port         = 2377
  to_port           = 2377
  protocol          = "tcp"
  self              = true
}

resource "aws_security_group_rule" "swarm_node_tcp" {
  type              = "ingress"
  security_group_id = aws_security_group.swarm.id
  description       = "Swarm node communication"
  from_port         = 7946
  to_port           = 7946
  protocol          = "tcp"
  self              = true
}

resource "aws_security_group_rule" "swarm_node_udp" {
  type              = "ingress"
  security_group_id = aws_security_group.swarm.id
  description       = "Swarm node communication (UDP)"
  from_port         = 7946
  to_port           = 7946
  protocol          = "udp"
  self              = true
}

resource "aws_security_group_rule" "overlay_network" {
  type              = "ingress"
  security_group_id = aws_security_group.swarm.id
  description       = "Overlay network"
  from_port         = 4789
  to_port           = 4789
  protocol          = "udp"
  self              = true
}

resource "aws_security_group_rule" "all_egress" {
  type              = "egress"
  security_group_id = aws_security_group.swarm.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_iam_role" "swarm" {
  count              = var.create_instance_profile ? 1 : 0
  name               = "${var.ec2_instance_name}-role"
  assume_role_policy = data.aws_iam_policy_document.swarm_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "swarm" {
  for_each   = var.create_instance_profile ? toset(var.instance_profile_policy_arns) : []
  role       = aws_iam_role.swarm[0].name
  policy_arn = each.value
}

resource "aws_iam_instance_profile" "swarm" {
  count = var.create_instance_profile ? 1 : 0
  name  = "${var.ec2_instance_name}-profile"
  role  = aws_iam_role.swarm[0].name
  tags  = var.tags
}

resource "aws_instance" "node" {
  count                       = var.instance_count
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  associate_public_ip_address = var.public_ip_associate
  key_name                    = var.key_name
  vpc_security_group_ids      = [aws_security_group.swarm.id]
  subnet_id                   = element(var.subnet_ids, count.index % length(var.subnet_ids))
  iam_instance_profile        = var.create_instance_profile ? aws_iam_instance_profile.swarm[0].name : null

  root_block_device {
    volume_size = 15
    volume_type = "gp3"
  }

  user_data = file("${path.module}/user-data.sh")

  tags = merge(var.tags, { Name = "${var.ec2_instance_name}-${count.index + 1}" })
}
