variable "sensor_log_volume_name" {
  description = "Name of the Log Volume. The sensor root looks it up by this name"
  type        = string
  default     = "sensor-logs"
}

variable "sensor_log_volume_size" {
  description = "Size of the Log Volume in GB"
  type        = number
  default     = 50
}

variable "location" {
  description = "Hetzner location of the Log Volume. Must match the location of the Sensor"
  type        = string
  default     = "fsn1"
}

variable "labels" {
  description = "Labels applied to the Log Volume"
  type        = map(string)
  default = {
    env        = "honeynet"
    management = "terraform"
  }
}
