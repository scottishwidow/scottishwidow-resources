output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_zone-1" {
  value = module.vpc.private_zone-1
}

output "private_zone-2" {
  value = module.vpc.private_zone-2
}

output "public_zone-1" {
  value = module.vpc.public_zone-1
}