ephemeral "random_password" "db_password" {
  length = 16
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_password" {
  name = var.db_password_secret_name
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string_wo = ephemeral.random_password.db_password.result
  secret_string_wo_version = 1
}

ephemeral "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
}

resource "aws_db_subnet_group" "postgres" {
  name = "${var.postgres_instance_identifier}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = var.tags
}

resource "aws_security_group" "postgres" {
  name = var.postgres_sg_name
  description = "Allow traffic to RDS for Postgres"
  vpc_id = var.vpc_id
  tags = var.tags
}

resource "aws_db_instance" "postgres" {
  count = var.create_postgres ? 1 : 0
  identifier = var.postgres_instance_identifier
  db_subnet_group_name = aws_db_subnet_group.postgres.name
  publicly_accessible = var.is_public
  instance_class = var.postgres_instance_class
  allocated_storage = var.postgres_storage
  vpc_security_group_ids = [ aws_security_group.postgres.id ]
  availability_zone = var.postgres_az
  engine = "postgres"
  username = var.postgres_username
  skip_final_snapshot = var.postgres_skip_final_snapshot
  password_wo = ephemeral.aws_secretsmanager_secret_version.db_password.secret_string
  password_wo_version = aws_secretsmanager_secret_version.db_password.secret_string_wo_version
}

# TODO Security Group for Postgres