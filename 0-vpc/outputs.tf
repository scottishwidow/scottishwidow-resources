output "vpc_id" {
  value = module.vpc.vpc_id.id
}

output "private_zone-1" {
  value = module.vpc.private_zone-1.id
}

output "private_zone-2" {
  value = module.vpc.private_zone-2.id
}

output "public_zone-1" {
  value = module.vpc.public_zone-1.id
}