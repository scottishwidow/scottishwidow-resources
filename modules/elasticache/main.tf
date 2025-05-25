resource "aws_security_group" "redis_security_group" {
  name = "redis-security-group"
  description = "Security Group for Redis Instance"
  vpc_id = data.aws_vpc.selected.id

  ingress {
    from_port = 6379
    to_port = 6379
    protocol = "tcp"
    security_groups = [ data.aws_security_group.wordpress_sg.id ]
  }
}

resource "aws_elasticache_subnet_group" "redis_subnet_group" {
  name = "redis-subnet-group"
  subnet_ids = [ data.aws_subnet.selected_one.id, data.aws_subnet.selected_two.id ]
}

resource "aws_elasticache_cluster" "redis_cache" {
  cluster_id = var.cluster_id
  engine = "redis"
  node_type = "cache.t4g.micro"
  num_cache_nodes = 1
  parameter_group_name = var.parameter_group_name
  engine_version = var.engine_version
  port = 6379
  subnet_group_name = aws_elasticache_subnet_group.redis_subnet_group.name
  security_group_ids = [ aws_security_group.redis_security_group.id ]
  
  depends_on = [ aws_elasticache_subnet_group.redis_subnet_group ]
}