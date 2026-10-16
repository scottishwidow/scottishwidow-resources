output "vpc_id" {
  description = "ID of the management VPC."
  value       = module.vpc.vpc_id
}

output "public_zone_1" {
  description = "ID of the public subnet that hosts Nextcloud."
  value       = module.vpc.public_zone_1
}
