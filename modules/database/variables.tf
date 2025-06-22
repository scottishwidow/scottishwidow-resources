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
  default = "db.t3.micro"
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
  default = true
}

variable "is_public" {
  type = bool
  default = true
}

variable "create_postgres" {
  type = bool
  default = false
}

variable "postgres_az" {
  type = string
  default = "eu-central-1b"
}