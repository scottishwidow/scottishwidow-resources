resource "hcloud_volume" "sensor_logs" {
  name              = var.sensor_log_volume_name
  size              = var.sensor_log_volume_size
  location          = var.location
  format            = "ext4"
  delete_protection = true
  labels            = var.labels
}
