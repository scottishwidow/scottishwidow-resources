resource "aws_db_subnet_group" "rds_subnet_group" {
  name = "rds-subnet-group"
  subnet_ids = [ data.aws_subnet.selected.id ]
}

resource "aws_security_group" "rds_security_group" {
  name = "rds-security-group"
  description = "Security Group for RDS Instance"
  vpc_id = data.aws_vpc.selected.id

  ingress {
    from_port = 3306
    to_port = 3306
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # todo (must be EC2 security group)
  }
}

resource "aws_db_instance" "rds_instance" {
  engine = "mysql"
  engine_version = var.mysql_engine_version
  skip_final_snapshot = true
  final_snapshot_identifier = var.final_snapshot_identifier
  instance_class = "db.t2.micro"
  allocated_storage = 20
  identifier = var.instance_identifier
  db_name = var.db_name
  username = var.db_username
  password = var.db_password
  db_subnet_group_name = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [ aws_secutiry_group.rds_security_group.id ]

  tags = var.tags
}