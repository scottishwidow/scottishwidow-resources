variable "mysql_engine_version" {
  type = string
  description = "MySQL Engine Version"
  default = "8.4.3"
}

variable "final_snapshot_identifier" {
  type = string
  description = "RDS Final Snapshot Identifier"
  default = "final-snapshot"
}

variable "instance_identifier" {
  type = string
  description = "RDS Instance Identifier"
  default = "rds-instance"
}

variable "db_name" {
  type = string
  description = "MySQL Database Name"
  default = "value"
}

variable "db_username" {
  type = string
  description = "Database Username"
}

variable "db_password" {
  type = string
  description = "Database Password"
}

variable "tags" {
  type = map(any)
  description = "RDS Instance Tags"
}