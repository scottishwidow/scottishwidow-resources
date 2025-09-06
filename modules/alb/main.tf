###########################
# Common
###########################

resource "aws_security_group" "alb_sg" {
  name = var.alb_sg_name
  description = "Allow HTTP and HTTPS traffic"
  vpc_id = var.vpc_id
}

resource "aws_lb" "alb" {
  name = "${var.env}-${var.alb_name}"
  internal = false
  load_balancer_type = "application" 
  security_groups = [aws_security_group.alb_sg.id]
  subnets = var.alb_subnets

  enable_deletion_protection = var.alb_deletion_protection
  idle_timeout = var.alb_idle_timeout
  enable_cross_zone_load_balancing = var.alb_cross_zone_load_balancing

  tags = var.tags
}