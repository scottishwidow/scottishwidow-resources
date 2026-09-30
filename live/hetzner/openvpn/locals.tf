locals {
  gateway_labels = merge(var.labels, { role = "gateway" })
}
