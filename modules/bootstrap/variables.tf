variable "region" {
  description = "AWS region for bootstrap"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  type        = string
  description = "Project name"
  default     = "scottishwidow"
}

variable "env" {
  type        = string
  description = "Environment name"
  default     = "dev"
}

variable "tags" {
  description = "Project tags"
  type        = map(any)
}

variable "object_lock_enabled" {
  description = "Enable object S3 object locking"
  type        = bool
  default     = true
}