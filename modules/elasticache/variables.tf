variable "cluster_id" {
  type = string
  description = "Redis Cluster for Wordpress session caching"
  default = "wordpress-redis"
}

variable "parameter_group_name" {
  type = string
  description = "Parameter Group for Redis to use"
  default = "default.redis7"
}

variable "engine_version" {
  type = string
  description = "Redis Engine Version"
  default = "7.1"
}

variable "region" {
  type = string
  description = "AWS Region for RDS"
  default = "eu-west-1"
}