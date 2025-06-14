variable "db_password_secret_name" {
  type = string
}

variable "postgres_instance_identifier" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "subnet_ids" {
  type = list(string)
}

variable "postgres_instance_class" {
  type = string
  default = "t2.micro"
}

variable "postgres_storage" {
  type = number
  default = 10
}

variable "postgres_username" {
  type = string
  default = "postgres"
}

variable "postgres_skip_final_snapshot" {
  type = bool
  default = false
}
