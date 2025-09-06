###########################
# Common
###########################

variable "env" {
  description = "Deployment environment prefix (dev, stage, prod)"
  type = string
}

variable "tags" {
  description = "Common tags to apply to all ALB resources"
  type = map(string)
}

variable "alb_sg_name" {
  description = "Name of the Security Group associated with the ALB"
}

variable "vpc_id" {
  description = "ID of the VPC where ALB resources are deployed"
  type = string
}

variable "alb_subnets" {
  description = "List of subnet IDs where the Application Load Balancer will be deployed"
  type = list(string)
}

variable "alb_name" {
  description = "Name of the ALB"
  type = string
  default = "scottishwidow"
}

variable "alb_deletion_protection" {
  description = "Used to enable / disable deletion protection for the ALB"
  type = bool
  default = false
}

variable "alb_cross_zone_load_balancing" {
  description = "Used to enable / disable cross zone load balancing for the ALB"
  type = bool
  default = false
}

variable "alb_idle_timeout" {
  description = "Time in seconds that the connection is allowed to be idle"
  type = number
  default = 60
}